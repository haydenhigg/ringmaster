import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from openai import OpenAI

# constants
DB = 'db.sqlite'
MODEL = 'gpt-4o'
# FUNCTION_CALL_LIMIT = 20

# util
def make_timestamp() -> str:
    return datetime \
        .now(ZoneInfo('America/New_York')) \
        .strftime('%b %-d %Y at %-I:%M %p %Z')

# functions
def store_memory(content: str, tags: set[str]) -> str:
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO memories (time, content)
        VALUES (?, ?)
    ''', (make_timestamp(), content))

    memory_id = cursor.lastrowid

    cursor.executemany('''
        INSERT INTO memory_tags (memory_id, tag)
        VALUES (?, ?)
    ''', [(memory_id, tag) for tag in tags])

    connection.commit()

    return 'success'

def retrieve_memories(tags: set[str]) -> str:
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    result = cursor.execute(f'''
        SELECT
            m.id,
            m.time,
            m.content,
            GROUP_CONCAT(mt.tag) AS tags
        FROM memories m
        JOIN memory_tags mt ON m.id = mt.memory_id
        WHERE mt.tag IN (''' +  ','.join('?' * len(tags)) + ''')
        GROUP BY m.id
        HAVING COUNT(DISTINCT mt.tag) = ?
        ORDER BY m.id DESC
    ''', [*tags, len(tags)])
    rows = result.fetchall()

    memories = [{'id': r[0], 'time': r[1], 'content': r[2]} for r in rows]

    return json.dumps(memories)

def list_memory_tags() -> str:
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    result = cursor.execute(f'''
        SELECT DISTINCT mt.tag
        FROM memory_tags mt
        JOIN memories m ON mt.memory_id = m.id
        ORDER BY m.id DESC
    ''')
    rows = result.fetchall()

    return json.dumps(rows)

# private
def call_function(
    call_id: str,
    function_name: str,
    function_arguments: str
) -> str:
    # log it
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO function_calls (time,
                                    call_id,
                                    function_name,
                                    function_arguments)
        VALUES (?, ?, ?, ?)
    ''', (make_timestamp(), call_id, function_name, function_arguments))

    connection.commit()

    # return function output
    args = json.loads(function_arguments)

    match function_name:
        case 'store_memory':
            return store_memory(args['content'], set(args['tags']))
        case 'retrieve_memories':
            return retrieve_memory(set(args['tags']))
        case 'list_memory_tags':
            return list_memory_tags()

    return f'failure: {function_name} is not a function'

def save_output(content: str):
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO outputs (time, content)
        VALUES (?, ?)
    ''', (make_timestamp(), content))

    connection.commit()

if __name__ == '__main__':
    with open('tools.json') as f:
        tools = json.load(f)

    with open('directive.txt') as f:
        context = [{'role': 'developer', 'content': f.read()}]

    client = OpenAI()
    is_response_needed = True

    while is_response_needed:
        response = client.responses.create(
            model=MODEL,
            tools=tools,
            input=context
        )

        is_response_needed = False

        for tool_call in response.output:
            if tool_call.type != "function_call":
                continue

            context.append(tool_call)
            context.append({
                'type': 'function_call_output',
                'call_id': tool_call.call_id,
                'output': call_function(
                    tool_call.call_id,
                    tool_call.name,
                    tool_call.arguments
                )
            })

            is_response_needed = True

    save_output(response.output_text)
    print(response.output_text)
