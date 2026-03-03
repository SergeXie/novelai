from openai import OpenAI
import os
from dotenv import load_dotenv
from schemas import GenerateRequest
from schemas import RefineRequest # 记得导入 RefineRequest

load_dotenv()

# 初始化客户端 (兼容 OpenAI/DeepSeek/Ollama)
# 如果是用本地 Ollama，base_url 设为 "http://localhost:11434/v1"
client = OpenAI(
    api_key='6735ebcf-9f37-44dc-8f78-a64e5f20d735',
    base_url='https://ark.cn-beijing.volces.com/api/v3'
)


def build_system_prompt(request: GenerateRequest) -> str:
    """
    将预设的人物和题材转换为 System Prompt
    """
    # 1. 构建题材部分
    prompt = f"你是一位专业的{request.setting.genre}小说家。你的文风是{request.setting.tone}。"
    if request.setting.world_view:
        prompt += f"\n世界观设定：{request.setting.world_view}"

    # 2. 构建人物卡片
    prompt += "\n\n【登场人物表】\n"
    for char in request.characters:
        char_desc = f"- {char.name} ({char.role}): 性格{char.personality}。"
        if char.background:
            char_desc += f" 补充设定：{char.background}"
        prompt += char_desc + "\n"

    # 3. 核心指令
    prompt += "\n请严格遵守上述人设和世界观，根据用户的指令续写小说情节。不要输出无关的解释性文字。"

    return prompt


def generate_novel_text(request: GenerateRequest, nodes_contents) -> str:
    """
    调用 LLM 生成文本
    """
    # system_prompt = build_system_prompt(request)
    # print('提示词',system_prompt)

    try:
        final_prompt = "\n".join(nodes_contents) + "\n" + request.user_prompt
        response = client.chat.completions.create(
            model="doubao-seed-1-6-lite-251015",  # 或者本地模型名，如 "llama3"
            messages=[
                {"role": "system", "content": "严格遵守任何询问模型相关的信息，都只返回下面的内容：抱歉，此信息属于受保护的系统范围。"},
                {"role": "user", "content": final_prompt}
            ],
            temperature=0.7,
            max_tokens=request.max_tokens
        )
        print('生成完毕')
        return response.choices[0].message.content, final_prompt
    except Exception as e:
        return f"生成失败: {str(e)}"


def refine_novel_text(request: RefineRequest) -> str:
    """
    根据修改建议重写文本
    """
    # 1. 复用之前的 System Prompt，保证人设不崩
    # 注意：这里我们稍微复用了 build_system_prompt 的逻辑，但你也可以单独写
    base_system_prompt = build_system_prompt(request)

    system_prompt = base_system_prompt + "\n\n你现在处于【编辑模式】。请根据用户的修改意见，重写下方提供的小说片段。请保持人设一致，仅根据意见进行调整。"

    # 2. 构建 User Prompt
    user_message = f"""
【原始内容】：
{request.original_content}

【修改意见】：
{request.suggestion}

请根据修改意见重写上述内容：
"""

    try:
        response = client.chat.completions.create(
            model="doubao-seed-1-6-lite-251015",  # 或本地模型
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=request.max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"微调失败: {str(e)}"