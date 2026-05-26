"""Unit tests for prompt intent detection."""

from __future__ import annotations

import unittest

from llm.intent import PromptIntent, detect_prompt_intent


class DetectPromptIntentTests(unittest.TestCase):
    def test_factual_player_question_is_definitive(self) -> None:
        result = detect_prompt_intent(
            "How many targets did Ja'Marr Chase have in 2024?"
        )
        self.assertEqual(result.intent, PromptIntent.DEFINITIVE)

    def test_stats_lookup_is_definitive(self) -> None:
        result = detect_prompt_intent("Christian McCaffrey 2024 stats")
        self.assertEqual(result.intent, PromptIntent.DEFINITIVE)

    def test_passing_leader_question_is_definitive(self) -> None:
        result = detect_prompt_intent("Who led the NFL in passing yards in 2024?")
        self.assertEqual(result.intent, PromptIntent.DEFINITIVE)

    def test_opinion_question_is_conversational(self) -> None:
        result = detect_prompt_intent(
            "What do you think about the Bills playoff chances?"
        )
        self.assertEqual(result.intent, PromptIntent.CONVERSATIONAL)

    def test_greeting_is_conversational(self) -> None:
        result = detect_prompt_intent("Hello, can you help me?")
        self.assertEqual(result.intent, PromptIntent.CONVERSATIONAL)

    def test_creative_request_is_conversational(self) -> None:
        result = detect_prompt_intent("Write a poem about fantasy football")
        self.assertEqual(result.intent, PromptIntent.CONVERSATIONAL)

    def test_empty_prompt_is_conversational(self) -> None:
        result = detect_prompt_intent("   ")
        self.assertEqual(result.intent, PromptIntent.CONVERSATIONAL)


if __name__ == "__main__":
    unittest.main()
