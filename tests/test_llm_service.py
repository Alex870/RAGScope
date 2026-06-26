import unittest
from importlib.util import find_spec


if find_spec("fastapi"):
    from server.services.llm_service import extract_context_length, parse_json_object, parse_context_window_error
else:
    extract_context_length = None
    parse_json_object = None
    parse_context_window_error = None


@unittest.skipUnless(parse_json_object is not None, "fastapi is not installed in this environment")
class LlmServiceTests(unittest.TestCase):
    def test_parse_json_object_extracts_first_object_from_wrapped_text(self) -> None:
        parsed = parse_json_object("prefix ```json\n{\"summary\": \"ok\"}\n``` suffix")
        self.assertEqual(parsed, {"summary": "ok"})

    def test_extract_context_length_checks_common_metadata_shapes(self) -> None:
        model_info = {"context_length": None, "details": {"max_context_length": "32768"}}
        self.assertEqual(extract_context_length(model_info), 32768)

    def test_parse_context_window_error_reads_token_count(self) -> None:
        message = "This model's maximum context length is 4096 tokens, but 8120 tokens were requested."
        self.assertEqual(parse_context_window_error(message), 4096)


if __name__ == "__main__":
    unittest.main()
