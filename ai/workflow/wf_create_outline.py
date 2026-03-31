from typing import List

from ai.workflow.base import BaseWorkflow, WorkflowStep


class CreateOutlineWorkflow(BaseWorkflow):
    """脑洞生成角色、世界观和大纲"""

    def get_steps(self) -> List[WorkflowStep]:
        return [
            WorkflowStep(
                name="people",
                prompt=(
                    "脑洞: {idea}\n"
                    "请基于这个脑洞生成 3-5 个核心角色。\n"
                    "用 JSON 输出，例如："
                    "{\"characters\": [{\"name\": \"...\", \"gender\": \"...\", \"age\": \"...\", "
                    "\"identity\": \"...\", \"personality\": \"...\", \"goal\": \"...\", \"conflict\": \"...\"}]}"
                ),
                system_prompt="你是一个只输出 JSON 的 API 接口，严禁返回任何自然语言描述。",
                temperature=0.8,
                output_key="book_people",
            ),
            WorkflowStep(
                name="world_setting",
                prompt=(
                    "脑洞: {idea}\n"
                    "角色设定: {book_people}\n"
                    "请生成适配该故事的世界观设定。\n"
                    "用 JSON 输出，例如："
                    "{\"world\": {\"era\": \"...\", \"background\": \"...\", \"core_rules\": [\"...\"], "
                    "\"major_forces\": [\"...\"], \"conflicts\": [\"...\"]}}"
                ),
                system_prompt="你是一个只输出 JSON 的 API 接口，严禁返回任何自然语言描述。",
                temperature=0.8,
                output_key="book_world",
            ),
            WorkflowStep(
                name="outline",
                prompt=(
                    "脑洞: {idea}\n"
                    "角色设定: {book_people}\n"
                    "世界观设定: {book_world}\n"
                    "请生成一个适合中文网络小说的故事大纲。\n"
                    "用 JSON 输出，例如："
                    "{\"outline\": {"
                    "\"theme\": \"...\", "
                    "\"main_line\": \"...\", "
                    "\"story_arcs\": ["
                    "{\"name\": \"开篇\", \"summary\": \"...\"}, "
                    "{\"name\": \"发展\", \"summary\": \"...\"}, "
                    "{\"name\": \"高潮\", \"summary\": \"...\"}"
                    "]}}"
                ),
                system_prompt="你是一个只输出 JSON 的 API 接口，严禁返回任何自然语言描述。",
                temperature=0.8,
                output_key="book_outline",
            ),
        ]