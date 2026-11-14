from tools.egm_knowledge import RECORD_SCHEMA, iter_records, load_schema, schema_errors


def test_invalid_created_at_is_rejected_by_schema_format_checker():
    _, source_record = iter_records()[0]
    record = dict(source_record)
    record["created_at"] = "not-a-date"

    errors = schema_errors(record, load_schema(RECORD_SCHEMA))

    assert any("created_at" in error and "date-time" in error for error in errors)
