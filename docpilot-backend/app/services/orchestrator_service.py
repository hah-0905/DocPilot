import json
from typing import Any

from app.services.llm_service import LLMService


class SolLunaOrchestrator:
    """Use GPT-6.1 Sol as supervisor and GPT-6 Luna as worker.

    Sol only plans, reviews, and decides whether Luna must revise. Luna performs
    the substantive work. Revision loops are bounded to avoid runaway token use.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        supervisor_model: str = "gpt-6.1-sol",
        worker_model: str = "gpt-6-luna",
        max_steps: int = 6,
        max_revisions: int = 2,
    ) -> None:
        self.llm = llm_service or LLMService()
        self.supervisor_model = supervisor_model
        self.worker_model = worker_model
        self.max_steps = max_steps
        self.max_revisions = max_revisions

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Parse JSON even when the model wraps it in a Markdown code fence."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return json.loads(cleaned)

    @staticmethod
    def _context_block(context: str | None) -> str:
        if not context:
            return "无额外上下文。"
        return context.strip()

    @staticmethod
    def _previous_outputs_block(outputs: dict[str, str]) -> str:
        if not outputs:
            return "无前置步骤结果。"

        # Keep the orchestration context bounded. Individual worker outputs can
        # otherwise grow until every later call becomes needlessly expensive.
        compact = json.dumps(outputs, ensure_ascii=False, indent=2)
        if len(compact) > 16000:
            compact = compact[-16000:]
        return compact

    async def _plan(self, task: str, context: str | None) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是总控 supervisor。你的职责只有：理解任务、拆解任务、定义验收标准。"
                    "不要亲自完成用户任务。把真正执行工作交给 worker。"
                    "只输出合法 JSON，不要 Markdown，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": f"""
用户任务：
{task}

可用上下文：
{self._context_block(context)}

请输出：
{{
  "summary": "一句话说明执行策略",
  "steps": [
    {{
      "id": "step-1",
      "task": "worker 要完成的具体任务",
      "acceptance_criteria": ["可检查的验收条件"],
      "depends_on": []
    }}
  ]
}}

约束：
1. steps 最多 {self.max_steps} 个；能少则少。
2. 每一步必须可以由 worker 独立执行或基于前置结果执行。
3. 不要把“规划”“检查”“总结计划”本身当作 worker 步骤。
4. 验收条件必须客观、可检查。
""".strip(),
            },
        ]
        raw = await self.llm.chat(
            messages=messages,
            model=self.supervisor_model,
            temperature=0.2,
            max_tokens=3000,
        )
        plan = self._extract_json(raw)
        steps = plan.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("Supervisor returned an invalid plan: missing steps")
        plan["steps"] = steps[: self.max_steps]
        return plan

    async def _execute_step(
        self,
        original_task: str,
        step: dict[str, Any],
        context: str | None,
        previous_outputs: dict[str, str],
        revision_feedback: str | None = None,
    ) -> str:
        feedback_block = (
            revision_feedback.strip()
            if revision_feedback
            else "这是第一次执行，没有返工意见。"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是执行 worker。只负责把分配给你的工作做完整。"
                    "不要重新规划整个项目，不要把任务退回 supervisor。"
                    "输出可以直接被后续步骤使用的实际结果。"
                ),
            },
            {
                "role": "user",
                "content": f"""
原始任务：
{original_task}

当前子任务：
{step.get('task', '')}

验收条件：
{json.dumps(step.get('acceptance_criteria', []), ensure_ascii=False, indent=2)}

额外上下文：
{self._context_block(context)}

前置步骤结果：
{self._previous_outputs_block(previous_outputs)}

Supervisor 返工意见：
{feedback_block}

请直接完成当前子任务。不要输出执行计划，不要声称稍后处理。
""".strip(),
            },
        ]
        return await self.llm.chat(
            messages=messages,
            model=self.worker_model,
            temperature=0.4,
            max_tokens=6000,
        )

    async def _review_step(
        self,
        original_task: str,
        step: dict[str, Any],
        worker_output: str,
    ) -> dict[str, str]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 supervisor，只做验收。不要替 worker 重写答案。"
                    "只输出合法 JSON，不要 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": f"""
原始任务：
{original_task}

子任务：
{step.get('task', '')}

验收条件：
{json.dumps(step.get('acceptance_criteria', []), ensure_ascii=False, indent=2)}

Worker 结果：
{worker_output}

判断结果是否满足验收条件，只输出：
{{
  "status": "pass" 或 "revise",
  "feedback": "若需返工，给出具体、可执行的修改要求；通过则简短说明"
}}
""".strip(),
            },
        ]
        raw = await self.llm.chat(
            messages=messages,
            model=self.supervisor_model,
            temperature=0.1,
            max_tokens=1500,
        )
        review = self._extract_json(raw)
        status = str(review.get("status", "revise")).lower()
        if status not in {"pass", "revise"}:
            status = "revise"
        return {
            "status": status,
            "feedback": str(review.get("feedback", "")),
        }

    async def _run_step_with_review(
        self,
        original_task: str,
        step: dict[str, Any],
        context: str | None,
        previous_outputs: dict[str, str],
    ) -> tuple[str, dict[str, str], int]:
        feedback: str | None = None
        last_review = {"status": "revise", "feedback": "not reviewed"}

        for revision_index in range(self.max_revisions + 1):
            output = await self._execute_step(
                original_task=original_task,
                step=step,
                context=context,
                previous_outputs=previous_outputs,
                revision_feedback=feedback,
            )
            last_review = await self._review_step(
                original_task=original_task,
                step=step,
                worker_output=output,
            )
            if last_review["status"] == "pass":
                return output, last_review, revision_index
            feedback = last_review["feedback"]

        return output, last_review, self.max_revisions

    async def _synthesize(
        self,
        task: str,
        context: str | None,
        outputs: dict[str, str],
        revision_feedback: str | None = None,
    ) -> str:
        feedback_block = revision_feedback or "这是第一次汇总，没有返工意见。"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是最终交付 worker。根据已经完成的子任务结果形成最终答案。"
                    "不要添加没有依据的新事实，不要描述内部调度过程。"
                ),
            },
            {
                "role": "user",
                "content": f"""
用户原始任务：
{task}

额外上下文：
{self._context_block(context)}

各子任务结果：
{self._previous_outputs_block(outputs)}

Supervisor 对最终交付的返工意见：
{feedback_block}

请输出可以直接交给用户的最终结果。
""".strip(),
            },
        ]
        return await self.llm.chat(
            messages=messages,
            model=self.worker_model,
            temperature=0.4,
            max_tokens=7000,
        )

    async def _review_final(self, task: str, final_answer: str) -> dict[str, str]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 supervisor，只做最终验收，不亲自重写。"
                    "只输出合法 JSON，不要 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": f"""
用户任务：
{task}

候选最终答案：
{final_answer}

检查：是否真正完成任务、是否遗漏关键要求、是否存在明显自相矛盾。
只输出：
{{
  "status": "pass" 或 "revise",
  "feedback": "具体返工要求；通过则简短说明"
}}
""".strip(),
            },
        ]
        raw = await self.llm.chat(
            messages=messages,
            model=self.supervisor_model,
            temperature=0.1,
            max_tokens=1500,
        )
        review = self._extract_json(raw)
        status = str(review.get("status", "revise")).lower()
        if status not in {"pass", "revise"}:
            status = "revise"
        return {
            "status": status,
            "feedback": str(review.get("feedback", "")),
        }

    async def run(
        self,
        task: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """Run one bounded supervisor/worker orchestration cycle."""
        if not task.strip():
            raise ValueError("task must not be empty")

        plan = await self._plan(task=task, context=context)
        outputs: dict[str, str] = {}
        step_results: list[dict[str, Any]] = []

        for index, step in enumerate(plan["steps"], start=1):
            step_id = str(step.get("id") or f"step-{index}")
            output, review, revisions = await self._run_step_with_review(
                original_task=task,
                step=step,
                context=context,
                previous_outputs=outputs,
            )
            outputs[step_id] = output
            step_results.append(
                {
                    "id": step_id,
                    "task": step.get("task", ""),
                    "output": output,
                    "review": review,
                    "revisions": revisions,
                }
            )

        final_feedback: str | None = None
        final_review = {"status": "revise", "feedback": "not reviewed"}
        final_answer = ""
        final_revisions = 0

        for revision_index in range(self.max_revisions + 1):
            final_answer = await self._synthesize(
                task=task,
                context=context,
                outputs=outputs,
                revision_feedback=final_feedback,
            )
            final_review = await self._review_final(
                task=task,
                final_answer=final_answer,
            )
            final_revisions = revision_index
            if final_review["status"] == "pass":
                break
            final_feedback = final_review["feedback"]

        return {
            "supervisor_model": self.supervisor_model,
            "worker_model": self.worker_model,
            "plan": plan,
            "steps": step_results,
            "final_answer": final_answer,
            "final_review": final_review,
            "final_revisions": final_revisions,
        }


sol_luna_orchestrator = SolLunaOrchestrator()
