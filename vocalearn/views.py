from django.conf import settings

from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from django.conf import settings

from pydub import AudioSegment

from azure.cognitiveservices.speech import SpeechConfig, AudioConfig, SpeechRecognizer, ResultReason
import azure.cognitiveservices.speech as speechsdk

import requests, json, difflib
import os, shutil, logging, time, string

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
def translate_text_view(request):
    cleanup_directory(audio_files_directory)
    if request.method == 'POST':
        path = '/translate'
        constructed_url = endpoint_text + path
        
        text = request.data.get("text")
        target_language = request.data.get("to")
        
        if not text or not target_language:
                return Response({"error": "Both 'text' and 'to' fields are required."}, status=400)
    
        headers = {
            "Ocp-Apim-Subscription-Key": text_api_key,
            "Ocp-Apim-Subscription-Region": 'global',
            "Content-Type": "application/json"
        }

        body = [{"text": text}]
        params = {"api-version": "3.0", "to": target_language}

        try:
            response = requests.post(constructed_url, headers=headers, json=body, params=params)
            
            if response.status_code == 200:
                translation = response.json()[0]["translations"][0]["text"]
                return Response({"translation": translation})
            else:
                return Response({"error": "Translation failed.", "details": response.json()}, status=response.status_code)
        
        except Exception as e:
            return Response({"error": "An error occurred.", "details": str(e)}, status=500)

    else:
        return Response({"error": "Invalid request method. Use POST."}, status=405)


@api_view(['POST'])
def speech_to_text_view(request):
    cleanup_directory(audio_files_directory)
    audio_file = request.FILES.get("audio")
    target_language = request.data.get('target_language')

    if not audio_file:
        return Response({"error": "No audio file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

    if not audio_file:
        return Response({"error": "No audio file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

    os.makedirs(audio_files_directory, exist_ok=True) 
    audio_file_path = os.path.join(audio_files_directory, audio_file.name)

    return get_continuous_transcription(audio_file, audio_file_path, audio_files_directory, target_language)
    
    
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


def get_continuous_transcription(audio_file, audio_file_path, audio_files_directory, target_language):
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=speech_services_key,
            region=region,
            speech_recognition_language=target_language,
        )
        audio_config = speechsdk.audio.AudioConfig(filename=get_processed_audio_file_path(
            audio_file, audio_file_path, audio_files_directory)
        )
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        recognized_text = []
        done = False

        def stop_cb(evt: speechsdk.SessionEventArgs):
            print("CLOSING on {}".format(evt))
            nonlocal done
            done = True

        speech_recognizer.recognizing.connect(lambda evt: print("RECOGNIZING: {}".format(evt.result.text)))
        speech_recognizer.recognized.connect(lambda evt: recognized_text.append(evt.result.text))
        speech_recognizer.session_started.connect(lambda evt: print("SESSION STARTED: {}".format(evt)))
        speech_recognizer.session_stopped.connect(lambda evt: print("SESSION STOPPED: {}".format(evt)))
        speech_recognizer.canceled.connect(lambda evt: print("CANCELED: {}".format(evt)))
        speech_recognizer.session_stopped.connect(stop_cb)
        speech_recognizer.canceled.connect(stop_cb)

        print("Starting continuous recognition")
        speech_recognizer.start_continuous_recognition()

        while not done:
            time.sleep(0.5)

        speech_recognizer.stop_continuous_recognition()
        full_transcription = " ".join(recognized_text)

        return Response({"status": "success", "transcription": full_transcription})

    except Exception as e:
        logger.error(f"Error during continuous recognition: {e}", exc_info=True)
        return Response({"error": f"Error during continuous recognition: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def pronunciation_assesment_view(request):
    cleanup_directory(audio_files_directory)
    
    audio_file = request.FILES.get('audio')
    os.makedirs(audio_files_directory, exist_ok=True) 
    
    audio_file_path = os.path.join(audio_files_directory, audio_file.name)

    speech_config = speechsdk.SpeechConfig(subscription=speech_services_key, region=speech_services_region)
    audio_config = speechsdk.audio.AudioConfig(filename=get_processed_audio_file_path(audio_file, audio_file_path, audio_files_directory))

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
        print('CLOSING on {}'.format(evt))
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
    else:
        return Response({"status": "success", "accuracyScore": accuracy_score, "prosodyScore": prosody_score,
                          "completenessScore": completeness_score, "fluency_score": fluency_score}, status=status.HTTP_200_OK)
    


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
            print(directory)
            shutil.rmtree(directory)
        
        os.makedirs(directory)
        return "Directory reset successfully."
    except Exception as e:
        return f"Error: {str(e)}"