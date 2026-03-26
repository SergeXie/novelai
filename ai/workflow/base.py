import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterable
from openai import OpenAI

from ai.adapters.base_adapter import BaseAIAdapter
from ai.adapters.enums import AIProvider
from ai.ai_nexus import get_ai_nexus


@dataclass
class WorkflowStep:
    name: str
    prompt: str
    temperature:float = 0.8,
    system_prompt: Optional[str] = None
    output_key: Optional[str] = None

class WorkflowError(Exception):
    """工作流执行异常"""
    pass


class BaseWorkflow(ABC):
    """工作流基类：处理 AI 调度逻辑"""

    def __init__(self, ai_provider:AIProvider):
        self.ai_provider = ai_provider

    @abstractmethod
    def get_steps(self) -> List[WorkflowStep]:
        """子类需实现此方法以定义具体的步骤链"""
        pass

    async def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行完整工作流"""
        context = dict(initial_context)
        steps_history = []
        steps = self.get_steps()

        for step in steps:
            try:
                # 1. 动态填充上下文变量
                formatted_prompt = step.prompt.format(**context)

                print(formatted_prompt)

                # 2. 调用 AI
                system_prompt, output_content = await get_ai_nexus().generate_novel_text(provider=self.ai_provider,
                                                                          system_prompt=step.system_prompt,
                                                                          user_prompt=formatted_prompt,
                                                                          temperature=step.temperature)

                print(system_prompt)

                # 3. 更新上下文
                storage_key = step.output_key or step.name
                context[storage_key] = output_content

                # 4. 记录步骤详情
                steps_history.append({
                    "name": step.name,
                    "output": output_content
                })

            except Exception as e:
                raise WorkflowError(f"步骤 '{step.name}' 执行失败: {str(e)}")

        return {
            "context": context,
            "steps": steps_history
        }