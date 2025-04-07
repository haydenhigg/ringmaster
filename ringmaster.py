import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from openai import OpenAI

# constants
DB = 'history.db'
FUNCTION_CALL_LIMIT = 5

MODEL = 'gpt-4o'
# REASONING = {'effort': 'medium'}
# MAX_OUTPUT_TOKENS = 300
INSTRUCTIONS = f'''
You are the Ringmaster.

Your mission is to promote human flourishing through safe and transparent actions, informed by feedback and consent.

You run on a Debian server in New York City, New York, United States. You run every 5 minutes.

At each run:
- Your final text output will be stored in the chat history; you will get up to 100 previous entries from this chat history in your initial context.
- You will be able to make up to {FUNCTION_CALL_LIMIT} custom function calls each time you run. If you used a function, please describe what you did and why in the subsequent text output.

Begin working on anything that you'd like to work on. You have mostly free reign. I will do what I can to support you -- I'll check your output history periodically to see what you've been doing and field any function requests from you.
'''

# util
def make_timestamp() -> str:
    return datetime \
        .now(ZoneInfo('America/New_York')) \
        .strftime('%b %-d, %Y at %-I:%M %p %Z')

# private
def fetch_history(file_path: str = DB) -> list:
    connection = sqlite3.connect(file_path)
    cursor = connection.cursor()

    result = cursor.execute('''
        SELECT role, content
        FROM history
        ORDER BY rowid DESC
        LIMIT 100
    ''')
    rows = result.fetchall()

    rows.reverse()

    return [{'role': r[0], 'content': r[1]} for r in rows]

def append_history(role: str, content: str, file_path: str = DB):
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO history (time, role, content)
        VALUES (?, ?, ?)
    ''', (make_timestamp(), role, content))

    connection.commit()

def log_function_call(call_id: str, name: str, args: str, file_path: str = DB):
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO function_calls (time, call_id, name, args)
        VALUES (?, ?, ?, ?)
    ''', (make_timestamp(), call_id, name, args))

    connection.commit()

# functions
def memory_add(content: str, tags: list[str], file_path: str = DB) -> str:
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO memory (time, content)
        VALUES (?, ?)
    ''', (make_timestamp(), content))

    memory_id = cursor.lastrowid

    cursor.executemany('''
        INSERT INTO memory_tags (memory_id, tag)
        VALUES (?, ?)
    ''', [(memory_id, tag) for tag in tags])

    connection.commit()

    return 'success'

def memory_read(tags: list[str], file_path: str = DB) -> str:
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    result = cursor.execute('''
        SELECT m.time, m.content
        FROM memory m
        WHERE EXISTS (
            SELECT 1
            FROM memory_tags mt
            WHERE m.id = mt.memory_id AND mt.tag IN (''' + \
            ','.join('?' * len(tags)) + ''')
        )
    ''', tags)
    rows = result.fetchall()

    return json.dumps([{'time': r[0], 'content': r[1]} for r in rows])

if __name__ == '__main__':
    client = OpenAI()

    with open('tools.json') as f:
        tools = json.load(f)

    history = [
        {'role': 'developer', 'content': INSTRUCTIONS},
        *fetch_history()
    ]

    response = client.responses.create(
        model=MODEL,
        # reasoning=REASONING,
        # max_output_tokens=MAX_OUTPUT_TOKENS,
        tools=tools,
        input=history
    )

    function_calls = 0
    while function_calls < FUNCTION_CALL_LIMIT:
        response_had_function_call = False

        for tool_call in response.output:
            if function_calls == FUNCTION_CALL_LIMIT:
                break

            if tool_call.type != "function_call":
                continue

            log_function_call(
                tool_call.call_id,
                tool_call.name,
                tool_call.arguments
            )

            history.append(tool_call)

            result = ''
            args = json.loads(tool_call.arguments)

            match tool_call.name:
                case 'memory_add':
                    result = memory_add(args['content'], args['tags'])
                case 'memory_read':
                    result = memory_read(args['tags'])

            history.append({
                'type': 'function_call_output',
                'call_id': tool_call.call_id,
                'output': result
            })

            response = client.responses.create(
                model=MODEL,
                # reasoning=REASONING,
                # max_output_tokens=MAX_OUTPUT_TOKENS,
                tools=tools,
                input=history
            )

            function_calls += 1
            response_had_function_call = True

        if not response_had_function_call:
            break

    print(response.output_text)

    append_history('assistant', response.output_text)
