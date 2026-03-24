# 启用注解的未来特性，让类型注解更规范（Python3.7+兼容）
from __future__ import annotations

# 导入标准库：命令行参数解析、JSON处理、系统环境变量
import argparse
import json
import os
# 导入数据类：简化实体类定义，无需手动写__init__
from dataclasses import dataclass
# 导入类型注解：定义任意类型、字典、可迭代对象、列表、可选类型
from typing import Any, Dict, Iterable, List, Optional

# 导入火山方舟适配的OpenAI SDK（火山方舟兼容OpenAI API格式）
from openai import OpenAI

from common.config.config import settings


# 自定义异常类：工作流步骤执行失败时抛出
class WorkflowError(Exception):
    """Raised when a workflow step cannot be executed."""


# 工作流步骤配置数据类：定义每一步AI调用的所有参数
@dataclass
class WorkflowStep:
    name: str              # 步骤名称（唯一标识）
    prompt: str            # 提示词模板（支持{变量}占位符）
    model: str             # 调用的AI模型名称
    temperature: float = 0.7  # 生成随机性（0=固定，1=最随机）
    max_tokens: Optional[int] = None  # 最大生成token数（可选）
    system: Optional[str] = None       # 自定义系统提示词（可选）
    output_key: Optional[str] = None   # 输出结果存储到上下文的key（可选）


# 单步骤执行结果数据类：存储步骤配置+输出内容
@dataclass
class StepResult:
    step: WorkflowStep  # 对应的步骤配置
    output: str         # AI返回的原始输出


# 整个工作流执行结果数据类
@dataclass
class WorkflowResult:
    context: Dict[str, Any]  # 上下文字典（存储所有步骤的输出，供后续步骤调用）
    steps: List[StepResult]  # 所有步骤的执行结果列表


# 构建火山方舟AI客户端（核心：配置API密钥和接口地址）
def build_client(api_key: Optional[str] = None, base_url: Optional[str] = None) -> OpenAI:
    """Create an OpenAI client configured for Volcengine Ark."""
    # 优先级：传入的api_key > 配置中的豆包API Key > 环境变量ARK_API_KEY
    api_key = api_key or settings.doubao.api_key or os.environ.get("ARK_API_KEY")
    # 优先级：传入的base_url > 配置中的豆包Base URL > 环境变量ARK_BASE_URL > 默认火山方舟地址
    base_url = base_url or settings.doubao.base_url or os.environ.get("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
    
    # 无API密钥则抛异常
    if not api_key:
        raise WorkflowError("Missing API key. Set DOUBAO__API_KEY/ARK_API_KEY or pass api_key explicitly.")
    
    # 创建并返回OpenAI客户端（兼容火山方舟）
    return OpenAI(api_key=api_key, base_url=base_url)


# 编程式调用小说生成工作流（封装版，返回可序列化的字典）
def run_novel_workflow(
    idea: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    default_system: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper to run the novel workflow programmatically and return a serializable dict."""
    # 构建AI客户端
    client = build_client(api_key=api_key, base_url=base_url)
    # 构建工作流步骤
    steps = build_steps(model or settings.doubao.model_name)

    # 执行工作流
    result = run_workflow(
        client=client,
        steps=steps,
        context={"idea": idea},  # 初始上下文：传入用户的小说脑洞
        default_system=default_system or "你是一位擅长中文网文的作家，保持连贯与可读性。",
    )

    # 返回格式化结果（上下文+步骤输出）
    return {
        "context": result.context,
        "steps": [{"name": s.step.name, "output": s.output} for s in result.steps],
    }


# 【核心函数】顺序执行工作流所有步骤，自动传递上下文
def run_workflow(
    client: OpenAI,
    steps: Iterable[WorkflowStep],
    context: Optional[Dict[str, Any]] = None,
    default_system: Optional[str] = None,
) -> WorkflowResult:
    """Execute steps sequentially, feeding each output into the context."""
    # 初始化上下文字典（存储所有步骤的输出，供后续步骤调用）
    ctx: Dict[str, Any] = dict(context or {})
    # 初始化步骤结果列表
    results: List[StepResult] = []

    # 遍历执行每一个工作流步骤
    for step in steps:
        try:
            # 格式化提示词：替换{变量}为上下文中的实际值
            formatted_prompt = step.prompt.format(**ctx)
        except KeyError as exc:
            # 提示词中缺少变量，抛异常
            raise WorkflowError(f"Missing variable '{exc.args[0]}' for step '{step.name}'") from exc

        # 构造AI对话消息
        messages = []
        # 系统提示词：步骤自定义 > 默认系统提示词
        system_text = step.system or default_system
        if system_text:
            messages.append({"role": "system", "content": system_text})
        # 用户提示词：格式化后的最终提示词
        messages.append({"role": "user", "content": formatted_prompt})

        # 调用AI接口生成内容
        completion = client.chat.completions.create(
            model=step.model,
            messages=messages,
            temperature=step.temperature,
            max_tokens=step.max_tokens,
        )

        # 获取AI返回的文本内容
        content = completion.choices[0].message.content
        # 确定结果存储key：自定义output_key > 步骤名称
        key = step.output_key or step.name
        # 将结果存入上下文（供后续步骤使用）
        ctx[key] = content
        # 保存步骤结果
        results.append(StepResult(step=step, output=content))

    # 返回整个工作流的最终结果
    return WorkflowResult(context=ctx, steps=results)


# 构建小说生成的工作流步骤（共2步：书名简介+角色）
def build_steps(model: str) -> List[WorkflowStep]:
    return [
        # 步骤1：根据脑洞生成小说书名+简介（要求JSON格式输出）
        WorkflowStep(
            name="title_and_blurb",
            prompt=(
                "脑洞: {idea}\n"
                "请基于这个脑洞生成一个中文网络小说的书名和简介。\n"
                "用 JSON 输出，字段为 title 和 blurb，例如 {{\"title\": \"...\", \"blurb\": \"...\"}}。"
            ),
            model=model,
            temperature=0.8,
            output_key="book_seed",  # 结果存入上下文的key：book_seed
        ),
        # 步骤2：根据书名简介生成3-4个小说角色（要求JSON格式输出）
        WorkflowStep(
            name="people",
            prompt=(
                "以下是书名和简介: {book_seed}\n"
                "请为这本小说生成3-4 个角色，保持紧凑的节奏。"
                " 用 JSON 输出，例如，JSON：{{\"characters\": [{{\"name\":\"..\", \"role\":\"..\"}}]}}。\n"
            ),
            model=model,
            temperature=0.8,
            output_key="book_people",  # 结果存入上下文的key：book_people
        ),
    ]


# 主函数：命令行入口，解析参数+执行工作流+打印结果
def main() -> None:
    # 初始化命令行参数解析器
    parser = argparse.ArgumentParser(description="Run a 3-step novel workflow.")
    # 必传参数：小说脑洞/主题
    parser.add_argument("idea", help="你的脑洞/主题，用于引导小说生成")
    # 可选参数：指定AI模型（默认值：doubao-seed-1-6-lite-251015）
    parser.add_argument("--model", default="doubao-seed-1-6-lite-251015", help="模型名称")
    # 可选参数：API密钥（优先读取环境变量ARK_API_KEY）
    parser.add_argument("--api-key", dest="api_key", help="Ark API key，默认取 ARK_API_KEY 环境变量")
    # 可选参数：自定义接口地址（默认火山方舟官方地址）
    parser.add_argument(
        "--base-url",
        default=None,
        help="可选自定义 Ark base URL，默认 https://ark.cn-beijing.volces.com/api/v3",
    )
    # 解析命令行参数
    args = parser.parse_args()

    # 构建AI客户端
    client = build_client(api_key=args.api_key, base_url=args.base_url)
    # 构建工作流步骤
    steps = build_steps(args.model)

    # 执行工作流
    result = run_workflow(
        client=client,
        steps=steps,
        context={"idea": args.idea},
        default_system="你是一位擅长中文网文的作家，保持连贯与可读性。",
    )

    # 遍历打印所有步骤的执行结果
    for step_result in result.steps:
        print("\n==>", step_result.step.name)
        print(step_result.output)
        # 下方是注释的JSON解析代码，取消注释可直接提取JSON字段
        # parsed = json.loads(step_result.output)
        # print("Parsed:", parsed)
        # print("Title:", parsed["title"])
        # print("Blurb:", parsed["blurb"])


# 程序入口：执行主函数
if __name__ == "__main__":
    main()
    # 命令行调用示例：
    # python -m workflow_runner.novel_workflow "重生的武大郎"