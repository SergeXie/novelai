from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ai.adapters.enums import AIProvider
from ai.ai_nexus import get_ai_nexus
from core.entity.vo.ai_response import AIWorkFlowResponse, AICompletionResponse


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
        self.name = "基础工作流"

    @abstractmethod
    def get_steps(self) -> List[WorkflowStep]:
        """子类需实现此方法以定义具体的步骤链"""
        pass

    async def run(self, initial_context: Dict[str, Any]) -> AIWorkFlowResponse:
        """执行完整工作流"""
        context = dict(initial_context)
        steps_history = []
        steps = self.get_steps()

        last_ai_output: Optional[AICompletionResponse] = None

        for step in steps:
            try:
                # 1. 动态填充上下文变量
                formatted_prompt = step.prompt.format(**context)

                # 2. 调用 AI
                ai_response: AICompletionResponse = await get_ai_nexus().generate_novel_text(provider=self.ai_provider,
                                                                          system_prompt=step.system_prompt,
                                                                          user_prompt=formatted_prompt,
                                                                          temperature=step.temperature)

                last_ai_output = ai_response

                # 3. 更新上下文
                storage_key = step.output_key or step.name
                context[storage_key] = ai_response.content

                # 4. 记录步骤详情
                steps_history.append(
                    {
                        "name": step.name,
                        "result": ai_response.model_dump()  # 关键：直接 dump 成纯字典
                    }
                )

            except Exception as e:
                raise WorkflowError(f"步骤 '{step.name}' 执行失败: {str(e)}")

        print("workflow steps history:", steps_history)

        clean_final_result = last_ai_output.model_dump() if last_ai_output else {}

        ret = AIWorkFlowResponse(
            context=context,
            steps=steps_history,
            final_result=clean_final_result
        )

        return ret

