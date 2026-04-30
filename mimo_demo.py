import os
from openai import OpenAI

client = OpenAI(
    api_key='sk-ckw164grofhhp0deqm484gagtpk265e85d1p0zd4wyw4dngz',
    base_url="https://api.xiaomimimo.com/v1"
)

completion = client.chat.completions.create(
    model="mimo-v2.5-pro",
    messages=[
        {
            "role": "system",
            "content": "你是一个有用的助手，协助用户解答问题和提供信息。请根据用户的提问，提供准确、简洁的回答。如果你不确定答案，可以说你不知道，但不要编造信息。"
        },
        {
            "role": "user",
            "content": "介绍一下米莫这个模型。"
        }
    ],
    max_completion_tokens=1024,
    temperature=1.0,
    top_p=0.95,
    stream=False,
    stop=None,
    frequency_penalty=0,
    presence_penalty=0
)

print(completion.model_dump_json())