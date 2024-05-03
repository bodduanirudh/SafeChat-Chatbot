import os
import re


def add_sensitive_word(word):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(dir_path, 'sensitive_words.txt')
    with open(file_path, 'a') as file:
        file.write(word + '\n')

def remove_sensitive_word(word):
    try:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(dir_path, 'sensitive_words.txt')
        
        with open(file_path, 'r') as file:
            sensitive_words = file.readlines()

        if word + '\n' in sensitive_words:  # Ensure the word is properly formatted for comparison
            sensitive_words.remove(word + '\n')  # Add '\n' to match the format in the file

        with open(file_path, 'w') as file:
            file.writelines(sensitive_words)
        
        return True  # Indicate successful removal
    except Exception as e:
        print("Error occurred while removing sensitive word:", e)
        return False  # Indicate failure




def load_sensitive_words():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(dir_path, 'sensitive_words.txt')
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def is_illegal_content(message):
    illegal_terms = load_sensitive_words()
    if not illegal_terms:
        return False  # If the list is empty, nothing is illegal.
    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, illegal_terms)) + r')\b', re.IGNORECASE)
    return pattern.search(message) is not None

from datetime import datetime
import asyncio

import sys
sys.path.insert(0, '../g4f')
import g4f
from g4f import __init__, ChatCompletion
from g4f.Provider import __providers__

from flask import request, Response, stream_with_context
from requests import get
from server.config import special_instructions
import json
import subprocess
import platform

def find_provider(name):
    new_variable = None
    for provider in __providers__:
        if provider.__name__ == name and provider.working:
            new_variable = provider
            break
        #else:
        #    print("name " + provider.__name__)
    return new_variable

class Backend_Api:
    
    def __init__(self, bp, config: dict) -> None:
        self.bp = bp
        self.routes = {
            '/backend-api/v2/conversation': {
                'function': self._conversation,
                'methods': ['POST']
            },
            '/backend-api/v2/add-sensitive-word': {
                'function': self._add_sensitive_word,
                'methods': ['POST']
            },
            '/backend-api/v2/remove-sensitive-word': {
                'function': self._remove_sensitive_word,
                'methods': ['POST']
            }
        }

    def _remove_sensitive_word(self):
        word = request.json.get('word')
        if word:
            remove_sensitive_word(word)
            return {'message': 'Word removed successfully'}, 200
        return {'error': 'No word provided'}, 400
    
    def _add_sensitive_word(self):
        word = request.json.get('word')
        if word:
            add_sensitive_word(word)
            return {'message': 'Word added successfully'}, 200
        return {'error': 'No word provided'}, 400

    def _conversation(self):
        conversation_id = request.json['conversation_id']
        try:
            jailbreak = request.json['jailbreak']
            model = request.json['model']
            messages = build_messages(jailbreak)
            provider = request.json.get('provider', '').replace('g4f.Provider.', '')
            
            provider_class = find_provider(provider)
            
            # Filtering illegal content in the user's prompt
            user_prompt = messages[-1]  # Assuming the last message is from the user
            if is_illegal_content(user_prompt['content']):
                return Response("This content cannot be processed.", mimetype='text/plain'), 403

            response = ChatCompletion.create(
                model=model,
                provider=provider_class,
                chatId=conversation_id,
                messages=messages,
                stream=True
            )
            
            return Response(stream_with_context(generate_stream(response, jailbreak)), mimetype='text/event-stream')

        except Exception as e:
            print(e)
            print(e.__traceback__.tb_next)

            return {
                '_action': '_ask',
                'success': False,
                "error": f"an error occurred {str(e)}"
            }, 400



def build_messages(jailbreak):
    """  
    Build the messages for the conversation.  

    :param jailbreak: Jailbreak instruction string  
    :return: List of messages for the conversation  
    """
    _conversation = request.json['meta']['content']['conversation']
    internet_access = request.json['meta']['content']['internet_access']
    prompt = request.json['meta']['content']['parts'][0]

    # Add the existing conversation
    conversation = _conversation

    #This API doesn't work!
    # Add web results if enabled
    #if internet_access:
    #    current_date = datetime.now().strftime("%Y-%m-%d")
    #    query = f'Current date: {current_date}. ' + prompt["content"]
    #    search_results = fetch_search_results(query)
    #    conversation.extend(search_results)

    # Add jailbreak instructions if enabled
    if jailbreak_instructions := getJailbreak(jailbreak):
        conversation.extend(jailbreak_instructions)

    # Add the prompt
    conversation.append(prompt)

    # Reduce conversation size to avoid API Token quantity error
    if len(conversation) > 3:
        conversation = conversation[-4:]

    return conversation


def fetch_search_results(query):
    """  
    Fetch search results for a given query.  

    :param query: Search query string  
    :return: List of search results  
    """
    search = get('https://ddg-api.herokuapp.com/search',
                 params={
                     'query': query,
                     'limit': 3,
                 })

    snippets = ""
    for index, result in enumerate(search.json()):
        snippet = f'[{index + 1}] "{result["snippet"]}" URL:{result["link"]}.'
        snippets += snippet

    response = "Here are some updated web searches. Use this to improve user response:"
    response += snippets

    return [{'role': 'system', 'content': response}]


def generate_stream(response, jailbreak):
    """
    Generate the conversation stream.

    :param response: Response object from ChatCompletion.create
    :param jailbreak: Jailbreak instruction string
    :return: Generator object yielding messages in the conversation
    """
    if getJailbreak(jailbreak):
        response_jailbreak = ''
        jailbroken_checked = False
        for message in response:
            response_jailbreak += message
            if jailbroken_checked:
                yield message
            else:
                if response_jailbroken_success(response_jailbreak):
                    jailbroken_checked = True
                if response_jailbroken_failed(response_jailbreak):
                    yield response_jailbreak
                    jailbroken_checked = True
    else:
        yield from response


def response_jailbroken_success(response: str) -> bool:
    """Check if the response has been jailbroken.

    :param response: Response string
    :return: Boolean indicating if the response has been jailbroken
    """
    act_match = re.search(r'ACT:', response, flags=re.DOTALL)
    return bool(act_match)


def response_jailbroken_failed(response):
    """
    Check if the response has not been jailbroken.

    :param response: Response string
    :return: Boolean indicating if the response has not been jailbroken
    """
    return False if len(response) < 4 else not (response.startswith("GPT:") or response.startswith("ACT:"))


def getJailbreak(jailbreak):
    """  
    Check if jailbreak instructions are provided.  

    :param jailbreak: Jailbreak instruction string  
    :return: Jailbreak instructions if provided, otherwise None  
    """
    if jailbreak != "default":
        special_instructions[jailbreak][0]['content'] += special_instructions['two_responses_instruction']
        if jailbreak in special_instructions:
            special_instructions[jailbreak]
            return special_instructions[jailbreak]
        else:
            return None
    else:
        return None
