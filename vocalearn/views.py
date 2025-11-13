from django.conf import settings
from django.db import models

from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status

from .models import Collection, CollectionItem, SavedItem, UserStorageQuota

from pydub import AudioSegment

from azure.cognitiveservices.speech import SpeechConfig, AudioConfig, SpeechRecognizer, ResultReason
import azure.cognitiveservices.speech as speechsdk
from azure.storage.blob import BlobServiceClient, ContentSettings

import requests, json, difflib
import os, shutil, logging, time, string
from datetime import datetime

speech_services_endpoint = settings.AZURE_SPEECH_ENDPOINT
speech_services_key = settings.AZURE_SPEECH_KEY
speech_services_region = 'southeastasia'

text_api_key=settings.AZURE_TRANSLATE_KEY
endpoint_text=settings.AZURE_TRANSLATE_API_ENDPOINT_TEXT
endpoint_document=settings.AZURE_TRANSLATE_API_ENDPOINT_DOCUMENT

region='southeastasia'

logger = logging.getLogger(__name__)

audio_files_directory = os.path.join(settings.MEDIA_ROOT, 'audio')

@api_view(['POST'])
@permission_classes([AllowAny])
def translate_text_view(request):
    cleanup_directory(audio_files_directory)
    
    path = '/translate'
    constructed_url = endpoint_text + path
    
    text = request.data.get("text")
    target_language = request.data.get("to")
    source_language = request.data.get("from", "")
    
    if not text or not target_language:
        return Response(
            {"error": "Both 'text' and 'to' fields are required."}, 
            status=400
        )

    headers = {
        "Ocp-Apim-Subscription-Key": text_api_key,
        "Ocp-Apim-Subscription-Region": 'global',
        "Content-Type": "application/json"
    }

    body = [{"text": text}]
    params = {"api-version": "3.0", "to": target_language}
    
    # Add source language if provided
    if source_language:
        params["from"] = source_language

    try:
        response = requests.post(constructed_url, headers=headers, json=body, params=params)
        
        if response.status_code == 200:
            translation_data = response.json()[0]
            translation = translation_data["translations"][0]["text"]
            detected_language = translation_data.get("detectedLanguage", {}).get("language", source_language)
            
            saved_item_id = None
            
            # Auto-save for authenticated users
            if request.user.is_authenticated:
                saved_item = SavedItem.objects.create(
                    user=request.user,
                    type='translation',
                    content={
                        "text": text,
                        "translation": translation,
                        "context": "",  # Can be added later by user
                        "alternatives": []  # Can be populated if API provides alternatives
                    },
                    source_language=detected_language,
                    target_language=target_language
                )
                saved_item_id = str(saved_item.id)
            
            return Response({
                "translation": translation,
                "detected_language": detected_language,
                "saved_item_id": saved_item_id,  # null for unauthenticated users
                "is_saved": saved_item_id is not None
            })
        else:
            return Response(
                {"error": "Translation failed.", "details": response.json()}, 
                status=response.status_code
            )
    
    except Exception as e:
        return Response(
            {"error": "An error occurred.", "details": str(e)}, 
            status=500
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def speech_to_text_view(request):
    cleanup_directory(audio_files_directory)
    audio_file = request.FILES.get("audio")
    target_language = request.data.get('target_language')

    if not audio_file:
        return Response({"error": "No audio file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

    os.makedirs(audio_files_directory, exist_ok=True) 
    audio_file_path = os.path.join(audio_files_directory, audio_file.name)

    return get_continuous_transcription(audio_file, audio_file_path, audio_files_directory, target_language, request)
    
    
def get_transcribed_text(audio_file, audio_file_path, audio_files_directory, target_language):
    try:
        speech_config = SpeechConfig(subscription=speech_services_key, region=region, speech_recognition_language=target_language)
        audio_config = AudioConfig(filename=get_processed_audio_file_path(audio_file, audio_file_path, audio_files_directory))
        recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
        result = recognizer.recognize_once()
        if result.reason == ResultReason.RecognizedSpeech:
            transcription = result.text
            cleanup_directory(audio_files_directory)
            return Response({"status": "success", "transcription": transcription})
        
        elif result.reason == ResultReason.NoMatch:
            cleanup_directory(audio_files_directory)
            return Response({"error": "No speech could be recognized."}, status=status.HTTP_400_BAD_REQUEST)
        
        else:
            cleanup_directory(audio_files_directory)
            return Response({"error": f"Speech recognition failed: {result.reason}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"Error processing the audio file: {e}", exc_info=True)
        return Response({"error": f"Error processing the audio file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_continuous_transcription(audio_file, audio_file_path, audio_files_directory, target_language, request=None):
    processed_audio_path = None
    audio_url = None
    
    try:
        # Get processed audio file path
        processed_audio_path = get_processed_audio_file_path(
            audio_file, audio_file_path, audio_files_directory
        )
        
        speech_config = speechsdk.SpeechConfig(
            subscription=speech_services_key,
            region=region,
            speech_recognition_language=target_language,
        )
        audio_config = speechsdk.audio.AudioConfig(filename=processed_audio_path)
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        recognized_text = []
        done = False

        def stop_cb(evt: speechsdk.SessionEventArgs):
            # print("CLOSING on {}".format(evt))
            nonlocal done
            done = True

        speech_recognizer.recognizing.connect(lambda evt: print("RECOGNIZING: {}".format(evt.result.text)))
        speech_recognizer.recognized.connect(lambda evt: recognized_text.append(evt.result.text))
        speech_recognizer.session_started.connect(lambda evt: print("SESSION STARTED: {}".format(evt)))
        speech_recognizer.session_stopped.connect(lambda evt: print("SESSION STOPPED: {}".format(evt)))
        speech_recognizer.canceled.connect(lambda evt: print("CANCELED: {}".format(evt)))
        speech_recognizer.session_stopped.connect(stop_cb)
        speech_recognizer.canceled.connect(stop_cb)

        # print("Starting continuous recognition")
        speech_recognizer.start_continuous_recognition()

        while not done:
            time.sleep(0.5)

        speech_recognizer.stop_continuous_recognition()
        full_transcription = " ".join(recognized_text)
        
        saved_item_id = None
        file_size_bytes = 0
        quota_info = None
        
        # Auto-save for authenticated users
        if request and request.user.is_authenticated:
            # Get user quota
            quota = get_or_create_user_quota(request.user)
            
            # Get file size before checking quota
            file_size_bytes = os.path.getsize(processed_audio_path)
            
            # Check if user can upload
            if not quota.can_upload(file_size_bytes):
                quota_info = {
                    "used_mb": round(quota.used_mb, 2),
                    "quota_mb": round(quota.quota_mb, 2),
                    "remaining_mb": round(quota.remaining_mb, 2),
                    "file_count": quota.audio_file_count,
                    "max_files": quota.max_audio_files
                }
                return Response({
                    "status": "success", 
                    "transcription": full_transcription,
                    "saved_item_id": None,
                    "is_saved": False,
                    "audio_url": None,
                    "quota_exceeded": True,
                    "quota_info": quota_info,
                    "message": "Storage quota exceeded. Unable to save audio file."
                })
            
            # Upload audio to Azure Blob Storage
            audio_url, uploaded_size = upload_audio_to_azure_storage(
                processed_audio_path, 
                request.user.id, 
                'speech_to_text'
            )
            
            if audio_url:
                # Create saved item
                saved_item = SavedItem.objects.create(
                    user=request.user,
                    type='speech_to_text',
                    content={
                        "transcription": full_transcription,
                        "original_filename": audio_file.name,
                        "duration": None,  # Can be calculated from audio file if needed
                    },
                    target_language=target_language,
                    audio_url=audio_url,
                    audio_size_bytes=uploaded_size
                )
                saved_item_id = str(saved_item.id)
                
                # Update user quota
                quota.add_file(uploaded_size)
                
                quota_info = {
                    "used_mb": round(quota.used_mb, 2),
                    "quota_mb": round(quota.quota_mb, 2),
                    "remaining_mb": round(quota.remaining_mb, 2),
                    "usage_percentage": round(quota.usage_percentage, 2),
                    "file_count": quota.audio_file_count,
                    "max_files": quota.max_audio_files
                }
        
        return Response({
            "status": "success", 
            "transcription": full_transcription,
            "saved_item_id": saved_item_id,
            "is_saved": saved_item_id is not None,
            "audio_url": audio_url,
            "quota_info": quota_info
        })

    except Exception as e:
        logger.error(f"Error during continuous recognition: {e}", exc_info=True)
        return Response({"error": f"Error during continuous recognition: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def pronunciation_assesment_view(request):
    cleanup_directory(audio_files_directory)
    
    audio_file = request.FILES.get('audio')
    os.makedirs(audio_files_directory, exist_ok=True) 
    
    audio_file_path = os.path.join(audio_files_directory, audio_file.name)
    processed_audio_path = None
    audio_url = None
    
    processed_audio_path = get_processed_audio_file_path(audio_file, audio_file_path, audio_files_directory)

    speech_config = speechsdk.SpeechConfig(subscription=speech_services_key, region=speech_services_region)
    audio_config = speechsdk.audio.AudioConfig(filename=processed_audio_path)

    reference_text = request.data.get('reference_text')
    enable_miscue = True
    enable_prosody_assessment = True
    
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=enable_miscue)
    
    if enable_prosody_assessment:
        pronunciation_config.enable_prosody_assessment()
    
    target_language = request.data.get('target_language')
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, language=target_language, audio_config=audio_config)
    pronunciation_config.apply_to(speech_recognizer)

    done = False
    recognized_words = []
    prosody_scores = []
    fluency_scores = []
    durations = []

    def stop_cb(evt: speechsdk.SessionEventArgs):
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""
        # print('CLOSING on {}'.format(evt))
        nonlocal done
        done = True

    def recognized(evt: speechsdk.SpeechRecognitionEventArgs):
        pronunciation_result = speechsdk.PronunciationAssessmentResult(evt.result)
        nonlocal recognized_words, prosody_scores, fluency_scores, durations
        recognized_words += pronunciation_result.words
        fluency_scores.append(pronunciation_result.fluency_score)
        if pronunciation_result.prosody_score is not None:
            prosody_scores.append(pronunciation_result.prosody_score)

        json_result = evt.result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
        jo = json.loads(json_result)
        nb = jo["NBest"][0]
        durations.append(sum([int(w["Duration"]) for w in nb["Words"]]))

    speech_recognizer.recognized.connect(recognized)
    speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
    speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
    speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    speech_recognizer.start_continuous_recognition()
    while not done:
        time.sleep(.5)

    if target_language == 'zh-CN':
        import jieba
        import zhon.hanzi
        jieba.suggest_freq([x.word for x in recognized_words], True)
        reference_words = [w for w in jieba.cut(reference_text) if w not in zhon.hanzi.punctuation]
    else:
        reference_words = [w.strip(string.punctuation) for w in reference_text.lower().split()]

    if enable_miscue:
        diff = difflib.SequenceMatcher(None, reference_words, [x.word.lower() for x in recognized_words])
        final_words = []
        for tag, i1, i2, j1, j2 in diff.get_opcodes():
            if tag in ['insert', 'replace']:
                for word in recognized_words[j1:j2]:
                    if word.error_type == 'None':
                        word._error_type = 'Insertion'
                    final_words.append(word)
            if tag in ['delete', 'replace']:
                for word_text in reference_words[i1:i2]:
                    word = speechsdk.PronunciationAssessmentWordResult({
                        'Word': word_text,
                        'PronunciationAssessment': {
                            'ErrorType': 'Omission',
                        }
                    })
                    final_words.append(word)
            if tag == 'equal':
                final_words += recognized_words[j1:j2]
    else:
        final_words = recognized_words

    final_accuracy_scores = []
    for word in final_words:
        if word.error_type == 'Insertion':
            continue
        else:
            final_accuracy_scores.append(word.accuracy_score)

    accuracy_score = sum(final_accuracy_scores) / len(final_accuracy_scores)
    
    
    if len(prosody_scores) == 0:
        prosody_score = "nan"
    else:
        prosody_score = sum(prosody_scores) / len(prosody_scores)
    
    fluency_score = sum([x * y for (x, y) in zip(fluency_scores, durations)]) / sum(durations)
    
    completeness_score = len([w for w in recognized_words if w.error_type == "None"]) / len(reference_words) * 100
    completeness_score = completeness_score if completeness_score <= 100 else 100
    speech_recognizer.stop_continuous_recognition()

    if not audio_file or not target_language or not reference_text:
        return Response({"error": "Something is missing"}, status=status.HTTP_400_BAD_REQUEST)
    
    saved_item_id = None
    quota_info = None
    
    # Auto-save for authenticated users
    if request.user.is_authenticated:
        # Get user quota
        quota = get_or_create_user_quota(request.user)
        
        # Get file size before checking quota
        file_size_bytes = os.path.getsize(processed_audio_path)
        
        # Check if user can upload
        if not quota.can_upload(file_size_bytes):
            quota_info = {
                "used_mb": round(quota.used_mb, 2),
                "quota_mb": round(quota.quota_mb, 2),
                "remaining_mb": round(quota.remaining_mb, 2),
                "file_count": quota.audio_file_count,
                "max_files": quota.max_audio_files
            }
            return Response({
                "status": "success", 
                "accuracyScore": accuracy_score, 
                "prosodyScore": prosody_score,
                "completenessScore": completeness_score, 
                "fluency_score": fluency_score,
                "saved_item_id": None,
                "is_saved": False,
                "audio_url": None,
                "quota_exceeded": True,
                "quota_info": quota_info,
                "message": "Storage quota exceeded. Unable to save audio file."
            }, status=status.HTTP_200_OK)
        
        # Upload audio to Azure Blob Storage
        audio_url, uploaded_size = upload_audio_to_azure_storage(
            processed_audio_path, 
            request.user.id, 
            'pronunciation'
        )
        
        if audio_url:
            # Create saved item with pronunciation assessment results
            saved_item = SavedItem.objects.create(
                user=request.user,
                type='pronunciation',
                content={
                    "reference_text": reference_text,
                    "accuracy_score": float(accuracy_score),
                    "prosody_score": float(prosody_score) if prosody_score != "nan" else None,
                    "completeness_score": float(completeness_score),
                    "fluency_score": float(fluency_score),
                    "original_filename": audio_file.name,
                    "words": [
                        {
                            "word": w.word,
                            "accuracy_score": w.accuracy_score,
                            "error_type": w.error_type
                        } 
                        for w in final_words
                    ]
                },
                target_language=target_language,
                audio_url=audio_url,
                audio_size_bytes=uploaded_size
            )
            saved_item_id = str(saved_item.id)
            
            # Update user quota
            quota.add_file(uploaded_size)
            
            quota_info = {
                "used_mb": round(quota.used_mb, 2),
                "quota_mb": round(quota.quota_mb, 2),
                "remaining_mb": round(quota.remaining_mb, 2),
                "usage_percentage": round(quota.usage_percentage, 2),
                "file_count": quota.audio_file_count,
                "max_files": quota.max_audio_files
            }
    
    return Response({
        "status": "success", 
        "accuracyScore": accuracy_score, 
        "prosodyScore": prosody_score,
        "completenessScore": completeness_score, 
        "fluency_score": fluency_score,
        "saved_item_id": saved_item_id,
        "is_saved": saved_item_id is not None,
        "audio_url": audio_url,
        "quota_info": quota_info
    }, status=status.HTTP_200_OK)
    


def get_processed_audio_file_path(audio_file, audio_file_path, audio_files_directory):
    try:
        with open(audio_file_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        processed_audio_path = os.path.join(audio_files_directory, "processed_" + audio_file.name)
        audio = AudioSegment.from_file(audio_file_path)
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        audio.export(processed_audio_path, format="wav")

        return processed_audio_path

    except Exception as e:
        return Response(None)


def cleanup_directory(directory):
    try:
        if os.path.exists(directory):
            # print(directory)
            shutil.rmtree(directory)
        
        os.makedirs(directory)
        return "Directory reset successfully."
    except Exception as e:
        return f"Error: {str(e)}"


def upload_audio_to_azure_storage(file_path, user_id, file_type='audio'):
    """
    Upload audio file to Azure Blob Storage and return the public URL and file size
    
    Args:
        file_path: Local path to the audio file
        user_id: User ID for organizing files
        file_type: Type of file (audio, processed_audio, etc.)
    
    Returns:
        tuple: (blob_url, file_size_bytes) or (None, 0) if failed
    """
    try:
        # Get connection string and container name from settings
        connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME
        
        if not connection_string:
            logger.error("Azure Storage connection string not configured")
            return None, 0
        
        # Get file size before upload
        file_size_bytes = os.path.getsize(file_path)
        
        # Create blob service client
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Create container if it doesn't exist
        try:
            container_client = blob_service_client.get_container_client(container_name)
            if not container_client.exists():
                container_client = blob_service_client.create_container(container_name)
        except Exception as e:
            logger.warning(f"Container might already exist: {e}")
            container_client = blob_service_client.get_container_client(container_name)
        
        # Generate unique blob name with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = os.path.splitext(file_path)[1]
        blob_name = f"users/{user_id}/{file_type}/{timestamp}_{os.path.basename(file_path)}"
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(
            container=container_name, 
            blob=blob_name
        )
        
        # Upload file with content type
        with open(file_path, "rb") as data:
            content_settings = ContentSettings(content_type='audio/wav')
            blob_client.upload_blob(
                data, 
                overwrite=True,
                content_settings=content_settings
            )
        
        # Return the blob URL and file size
        blob_url = blob_client.url
        logger.info(f"Audio file uploaded successfully to: {blob_url} (Size: {file_size_bytes} bytes)")
        return blob_url, file_size_bytes
        
    except Exception as e:
        logger.error(f"Error uploading audio to Azure Storage: {e}", exc_info=True)
        return None, 0


def get_or_create_user_quota(user):
    """Get or create user storage quota"""
    quota, created = UserStorageQuota.objects.get_or_create(
        user=user,
        defaults={
            'quota_bytes': 104857600,  # 100MB default
            'max_audio_files': 50
        }
    )
    return quota


@api_view(['POST'])
def add_item_to_collection(request, item_id):
    """Add a saved item to a collection"""
    collection_id = request.data.get("collection_id")
    
    if not collection_id:
        return Response({"error": "collection_id is required."}, status=400)
    
    try:
        saved_item = SavedItem.objects.get(id=item_id, user=request.user)
        collection = Collection.objects.get(id=collection_id, user=request.user)
        
        # Check if item already in collection
        if CollectionItem.objects.filter(collection=collection, item=saved_item).exists():
            return Response({"error": "Item already in this collection."}, status=400)
        
        # Get the next position
        max_position = CollectionItem.objects.filter(
            collection=collection
        ).aggregate(models.Max('position'))['position__max']
        
        next_position = (max_position or 0) + 1
        
        # Add to collection
        CollectionItem.objects.create(
            collection=collection,
            item=saved_item,
            position=next_position
        )
        
        # Update collection item count
        collection.update_item_count()
        
        return Response({
            "message": "Item added to collection successfully.",
            "collection_id": str(collection.id),
            "collection_name": collection.name
        })
    
    except SavedItem.DoesNotExist:
        return Response({"error": "Saved item not found."}, status=404)
    except Collection.DoesNotExist:
        return Response({"error": "Collection not found."}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['DELETE'])
def remove_item_from_collection(request, item_id, collection_id):
    """Remove a saved item from a collection"""
    try:
        saved_item = SavedItem.objects.get(id=item_id, user=request.user)
        collection = Collection.objects.get(id=collection_id, user=request.user)
        
        collection_item = CollectionItem.objects.get(
            collection=collection,
            item=saved_item
        )
        collection_item.delete()
        
        # Update collection item count
        collection.update_item_count()
        
        # Reorder remaining items
        remaining_items = CollectionItem.objects.filter(
            collection=collection
        ).order_by('position')
        
        for idx, item in enumerate(remaining_items, start=1):
            if item.position != idx:
                item.position = idx
                item.save(update_fields=['position'])
        
        return Response({
            "message": "Item removed from collection successfully."
        })
    
    except (SavedItem.DoesNotExist, Collection.DoesNotExist, CollectionItem.DoesNotExist):
        return Response({"error": "Item or collection not found."}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
def get_saved_items(request):
    """Get all saved items for authenticated user with optional filtering"""
    item_type = request.query_params.get('type')  # translation, speech_to_text, pronunciation
    search_query = request.query_params.get('search')
    
    items = SavedItem.objects.filter(user=request.user)
    
    if item_type:
        items = items.filter(type=item_type)
    
    if search_query:
        items = items.filter(
            models.Q(content__text__icontains=search_query) |
            models.Q(content__translation__icontains=search_query) |
            models.Q(content__transcription__icontains=search_query)
        )
    
    items_data = [
        {
            "id": str(item.id),
            "type": item.type,
            "content": item.content,
            "source_language": item.source_language,
            "target_language": item.target_language,
            "created_at": item.created_at,
            "collections": [
                {
                    "id": str(ci.collection.id),
                    "name": ci.collection.name
                }
                for ci in item.in_collections.select_related('collection')
            ]
        }
        for item in items
    ]
    
    return Response({
        "count": len(items_data),
        "items": items_data
    })


@api_view(['DELETE'])
def delete_saved_item(request, item_id):
    """Delete a saved item and free up storage quota"""
    try:
        saved_item = SavedItem.objects.get(id=item_id, user=request.user)
        
        # If item has audio, update quota
        if saved_item.audio_url and saved_item.audio_size_bytes > 0:
            quota = get_or_create_user_quota(request.user)
            quota.remove_file(saved_item.audio_size_bytes)
            
            # Optionally delete from Azure Blob Storage
            # delete_audio_from_azure_storage(saved_item.audio_url)
        
        saved_item.delete()
        
        return Response({
            "message": "Item deleted successfully."
        })
    
    except SavedItem.DoesNotExist:
        return Response({"error": "Saved item not found."}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
def get_user_quota(request):
    """Get user's current storage quota information"""
    quota = get_or_create_user_quota(request.user)
    
    return Response({
        "used_mb": round(quota.used_mb, 2),
        "quota_mb": round(quota.quota_mb, 2),
        "remaining_mb": round(quota.remaining_mb, 2),
        "usage_percentage": round(quota.usage_percentage, 2),
        "audio_file_count": quota.audio_file_count,
        "max_audio_files": quota.max_audio_files,
        "can_upload_more": quota.audio_file_count < quota.max_audio_files and quota.remaining_mb > 0
    })