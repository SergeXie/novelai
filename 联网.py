# import json
# import requests
# import certifi

# APIKEY = "n6rTGpANAOM3cjS0msLiic4C0khd5tw2"


# def websearch_by_apikey(body: dict):
#     # 请求URL
#     url = 'https://open.feedcoopapi.com/search_api/web_search'

#     # 请求头
#     headers = {
#         'Content-Type': 'application/json',
#         'Authorization': f'Bearer {APIKEY}'
#     }

#     try:
#         # 发送 POST 请求
#         response = requests.post(url, headers=headers, json=body, verify=certifi.where())
#         # print(f"Response Status Code: {response.status_code}")

#         if response.status_code == 200:
#             for line in response.iter_lines():
#                 if line:
#                     line_str = line.decode('utf-8')
#                     if "invalid_request" in line_str:
#                         return json.loads(response.text)
#                     print(line_str)

#     except Exception as e:
#         print(f"Error occurred: {str(e)}")


# if __name__ == "__main__":
#     body = {
#         "Query": "深圳今天天气",
#         # "SearchType": "web",
#         "SearchType": "web_summary",
#         "Count": 1,
#         "Filter": {
#             "NeedContent": False,
#             "NeedUrl": True
#         },
#         "NeedSummary": True
#     }

#     websearch_by_apikey(body=body)



#########################################################################
import os
from volcenginesdkarkruntime import Ark

api_key = '6735ebcf-9f37-44dc-8f78-a64e5f20d735'
client = Ark(
    base_url='https://ark.cn-beijing.volces.com/api/v3',
    api_key=api_key,
)

# 配置联网搜索工具
tools = [{
    "type": "web_search",
    "max_keyword": 2,  # 限制单轮搜索最大关键词数量，控制成本
}]

# 发起请求
response = client.responses.create(
    model="doubao-seed-2-0-pro-260215",
    input=[{"role": "user", "content": "张雪峰去世了么？"}],
    # tools=tools,
)

# print(response.output[0].content[0].text)
print(response)