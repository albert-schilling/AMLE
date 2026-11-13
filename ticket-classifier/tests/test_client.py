from ticket_classifier.client import upload_log


def test_upload_log_returns_the_file_id(mock_client, tmp_path):
    log = tmp_path / "app.log"
    log.write_text("x")
    mock_client.beta.files.upload.return_value.id = "file_9"

    assert upload_log(mock_client, log) == "file_9"
    name, data, _ = mock_client.beta.files.upload.call_args.kwargs["file"]
    assert (name, data) == ("app.log", b"x")
