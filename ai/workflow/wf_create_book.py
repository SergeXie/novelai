from typing import List

from ai.workflow.base import BaseWorkflow, WorkflowStep


class CreateBookWorkflow(BaseWorkflow):
    """小说创作工作流实现"""
    def init(self):
        self.name = "一键成书工作流"

    def get_steps(self) -> List[WorkflowStep]:
        return [
            # 步骤 1：生成标题与概要
            WorkflowStep(
                name="title_and_blurb",
                prompt=(
                    "脑洞: {idea}\n"
                    "请基于这个脑洞生成一个中文网络小说的书名和简介。\n"
                    "用 JSON 输出，字段为 title 和 blurb，例如 {{\"title\": \"...\", \"blurb\": \"...\"}}。"
                ),
                system_prompt="你是一个只输出 JSON 的 API 接口，严禁返回任何自然语言描述。",
                temperature=0.8,
                output_key="book_seed",
            ),
            # 步骤 2：基于步骤 1 的结果生成角色卡
            WorkflowStep(
                name="people",
                prompt=(
                    "以下是书名和简介: {book_seed}\n"
                    "请为这本小说生成3-4 个角色，保持紧凑的节奏。"
                    " 用 JSON 输出，例如，JSON：{{\"characters\": [{{\"name\":\"..\", \"role\":\"..\"}}]}}。\n"
                ),
                system_prompt="你是一个只输出 JSON 的 API 接口，严禁返回任何自然语言描述。",
                temperature=0.8,
                output_key="book_people",
            )
        ]