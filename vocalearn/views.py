from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from django.conf import settings

from pydub import AudioSegment

from azure.cognitiveservices.speech import SpeechConfig, AudioConfig, SpeechRecognizer, ResultReason

import requests
import os
import logging

speech_services_endpoint = 'https://southeastasia.api.cognitive.microsoft.com/'
speech_services_key = ''
speech_services_region = 'southeastasia'

text_api_key=''
endpoint_text='https://api.cognitive.microsofttranslator.com'
endpoint_document='https://vocalearn-translator.cognitiveservices.azure.com'

region='southeastasia'

logger = logging.getLogger(__name__)

@api_view(['POST'])
def translate_text_view(request):
    if request.method == 'POST':
        path = '/translate'
        constructed_url = endpoint_text + path
        
        text = request.data.get("text")
        target_language = request.data.get("to")
        
        if not text or not target_language:
                return Response({"error": "Both 'text' and 'to' fields are required."}, status=400)
    
        headers = {
            "Ocp-Apim-Subscription-Key": text_api_key,
            "Ocp-Apim-Subscription-Region": region,
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
    audio_file = request.FILES.get("audio")

    if not audio_file:
        return Response({"error": "No audio file uploaded."}, status=status.HTTP_400_BAD_REQUEST)


    audio_files_directory = os.path.join(settings.MEDIA_ROOT, 'audio')
    os.makedirs(audio_files_directory, exist_ok=True) 

    audio_file_path = os.path.join(audio_files_directory, audio_file.name)

    try:
        with open(audio_file_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)
    except Exception as e:
        logger.error(f"Error saving audio file: {str(e)}")
        return Response({"error": f"Error saving audio file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        # Configure Azure Speech SDK
        speech_config = SpeechConfig(subscription=speech_services_key, region=region)
        audio_config = AudioConfig(filename=audio_file_path)
        recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        # Perform speech recognition
        result = recognizer.recognize_once()
        print(result)
        if result.reason == ResultReason.RecognizedSpeech:
            transcription = result.text
            cleanup_result = cleanup_audio_files(audio_files_directory)
            logger.info(cleanup_result)
            return Response({"transcription": transcription})
        elif result.reason == ResultReason.NoMatch:
            cleanup_result = cleanup_audio_files(audio_files_directory)
            logger.info(cleanup_result)
            return Response({"error": "No speech could be recognized."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            cleanup_result = cleanup_audio_files(audio_files_directory)
            logger.info(cleanup_result)
            return Response({"error": f"Speech recognition failed: {result.reason}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error during speech recognition: {str(e)}")
        cleanup_result = cleanup_audio_files(audio_files_directory)
        logger.info(cleanup_result)
        return Response({"error": f"Error during speech recognition: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def recorded_audio(request):
    audio_file = request.FILES.get("audio")

    if not audio_file:
        return Response({"error": "No audio file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        audio_files_directory = os.path.join(settings.MEDIA_ROOT, 'audio')
        os.makedirs(audio_files_directory, exist_ok=True) 

        audio_file_path = os.path.join(audio_files_directory, audio_file.name)

        # Save the original file
        with open(audio_file_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        
        processed_audio_path = os.path.join(audio_files_directory, "processed_" + audio_file.name)
        audio = AudioSegment.from_file(audio_file_path)
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        audio.export(processed_audio_path, format="wav")        
        logger.debug(f"Processed audio saved at: {processed_audio_path}")

        # Optionally, remove the original file
        os.remove(audio_file_path)

        return Response({"status": "success", "processed_audio_path": processed_audio_path})

    except Exception as e:
        logger.error(f"Error processing the audio file: {e}", exc_info=True)
        return Response({"error": f"Error processing the audio file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def cleanup_audio_files(directory):
    try:
        files = os.listdir(directory)
        for file in files:
            if file.endswith('.wav'):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        return 'Cleaned up audio files.'
    except Exception as e:
        return f'Error: {str(e)}'


@api_view(['GET'])
def hello(request):
    return Response({'hello': "Hello Azure"}, status=200)


""" Working views: 
@api_view(['POST'])
def speech_to_text_view(request):
    audio_file = request.FILES.get("audio")
    if not audio_file:
        return Response({"error": "No audio file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

    # Save the audio file to the local directory
    audio_file_path = os.path.join(settings.MEDIA_ROOT, 'audio', audio_file.name)
    os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)  # Ensure the directory exists

    try:
        with open(audio_file_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)
    except Exception as e:
        logger.error(f"Error saving audio file: {str(e)}")
        return Response({"error": f"Error saving audio file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        # Configure Azure Speech SDK
        speech_config = SpeechConfig(subscription=speech_services_key, region=region)
        audio_config = AudioConfig(filename=audio_file_path)
        recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        # Perform speech recognition
        result = recognizer.recognize_once()
        print(result)
        if result.reason == ResultReason.RecognizedSpeech:
            return Response({"transcription": result.text})
        elif result.reason == ResultReason.NoMatch:
            return Response({"error": "No speech could be recognized."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": f"Speech recognition failed: {result.reason}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error during speech recognition: {str(e)}")
        return Response({"error": f"Error during speech recognition: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

"""