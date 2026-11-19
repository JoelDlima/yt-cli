"""Tests for the non-interactive Typer CLI commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ytdownloader import __version__
from ytdownloader.cli import app
from ytdownloader.history import HistoryManager
from ytdownloader.models import DownloadResult, Settings, VideoInfo

runner = CliRunner()


def test_version_flag_prints_version_and_exits():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_all_subcommands_and_option_descriptions():
    main_help = runner.invoke(app, ["--help"])
    assert main_help.exit_code == 0
    for cmd in ("download", "batch", "watch", "search", "history"):
        assert cmd in main_help.stdout

    batch_help = runner.invoke(app, ["batch", "--help"])
    assert batch_help.exit_code == 0
    assert "Download audio as MP3 instead of video." in batch_help.stdout
    assert "Video resolution" in batch_help.stdout

    search_help = runner.invoke(app, ["search", "--help"])
    assert search_help.exit_code == 0
    assert "Maximum number of search results" in search_help.stdout


def test_download_dry_run_displays_info_without_downloading(
    tmp_settings: Settings, mocker
):
    fake_info = VideoInfo(
        id="abc12345678",
        title="Dry Run Test Video",
        url="https://youtu.be/abc12345678",
        uploader="Test Channel",
        duration=90,
    )
    mocker.patch("ytdownloader.cli.get_config_manager").return_value.load.return_value = tmp_settings
    mocker.patch("ytdownloader.video.fetch_video_info", return_value=fake_info)
    mock_download = mocker.patch("ytdownloader.video.download_video")

    result = runner.invoke(app, ["download", "https://youtu.be/abc12345678", "--dry-run"])

    assert result.exit_code == 0
    assert "Dry Run Test Video" in result.stdout
    mock_download.assert_not_called()


def test_batch_command_downloads_and_records_history(
    tmp_settings: Settings, tmp_path: Path, mocker
):
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("https://youtu.be/dQw4w9WgXcQ\n", encoding="utf-8")

    fake_info = VideoInfo(
        id="dQw4w9WgXcQ",
        title="Batch Test Video",
        url="https://youtu.be/dQw4w9WgXcQ",
    )
    fake_result = DownloadResult(
        success=True,
        title="Batch Test Video",
        url="https://youtu.be/dQw4w9WgXcQ",
        output_path=str(tmp_path / "Batch Test Video.mp4"),
        file_size=1024,
    )
    hm = HistoryManager(path=tmp_path / "history.json")

    mocker.patch("ytdownloader.cli.get_config_manager").return_value.load.return_value = tmp_settings
    mocker.patch("ytdownloader.cli.get_history_manager", return_value=hm)
    mocker.patch("ytdownloader.video.fetch_video_info", return_value=fake_info)
    mocker.patch("ytdownloader.video.download_video", return_value=fake_result)

    result = runner.invoke(app, ["batch", str(urls_file), "--resolution", "720p"])

    assert result.exit_code == 0
    assert "1 succeeded" in result.stdout
    records = hm.load_all()
    assert len(records) == 1
    assert records[0].title == "Batch Test Video"
    assert records[0].resolution_or_bitrate == "720p"


def test_history_command_exports_csv(tmp_path: Path, mocker):
    hm = HistoryManager(path=tmp_path / "history.json")
    mocker.patch("ytdownloader.cli.get_history_manager", return_value=hm)
    export_file = tmp_path / "exported_history.csv"

    result = runner.invoke(app, ["history", "--export", str(export_file)])

    assert result.exit_code == 0
    assert export_file.exists()
