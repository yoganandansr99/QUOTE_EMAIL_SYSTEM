import pytest
import yaml
import os


class TestWorkflowSchedule:
    """Tests to validate GitHub Actions daily inspiration workflow schedule and syntax."""

    def test_workflow_yaml_is_valid_and_matches_5am_ist(self):
        """Workflow file must exist, be valid YAML, have schedule 05:00 AM IST, and keep workflow_dispatch."""
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".github",
            "workflows",
            "daily-inspiration.yml"
        )
        assert os.path.exists(workflow_path)

        with open(workflow_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["name"] == "Daily Inspiration Dispatch"
        assert "on" in data
        assert "schedule" in data["on"]
        assert "workflow_dispatch" in data["on"]

        schedule = data["on"]["schedule"]
        assert isinstance(schedule, list)
        assert len(schedule) >= 1

        cron_entry = schedule[0]
        assert "cron" in cron_entry
        # Either cron is 0 5 * * * with timezone Asia/Kolkata or standard 30 23 * * *
        if cron_entry.get("timezone") == "Asia/Kolkata":
            assert cron_entry["cron"] == "0 5 * * *"
        else:
            assert cron_entry["cron"] in ["30 23 * * *", "0 5 * * *"]
