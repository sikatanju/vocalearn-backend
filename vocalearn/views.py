from rest_framework.response import Response
from rest_framework.decorators import api_view

import requests

from .azure_translate_service import AzureTranslateService

key=''

endpoint_text='https://api.cognitive.microsofttranslator.com'
endpoint_document='https://vocalearn-translator.cognitiveservices.azure.com'

region='southeastasia'

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
            "Ocp-Apim-Subscription-Key": key,
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
    

@api_view(['GET'])
def hello(request):
    return Response({'hello': "Hello Azure"}, status=200)