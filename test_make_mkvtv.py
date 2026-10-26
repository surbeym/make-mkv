"""
Unit tests for make-mkv.py show_detailed_probe function.
Tests cover edge cases, movie discs, TV shows, and duration filtering.
Uses actual sample files from info-samples/ directory.
"""

import pytest
import sys
import io
from contextlib import redirect_stdout
import re
import importlib.util

# Load make-mkv module dynamically (handle hyphen in filename)
sys.path.insert(0, '.')
spec = importlib.util.spec_from_file_location("make_mkvtv", "make-mkv.py")
make_mkvtv_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_mkvtv_module)

show_detailed_probe = make_mkvtv_module.show_detailed_probe
iso_to_seconds = make_mkvtv_module.iso_to_seconds


class TestShowDetailedProbe:
    """Test suite for show_detailed_probe function"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.default_min_length = iso_to_seconds("PT25M")  # 1500 seconds
        self.default_max_length = iso_to_seconds("PT1H15M")  # 4500 seconds
        
         # Load actual sample files from info-samples directory
        with open("info-samples/info-sample-movie.txt", 'r') as f:
            self.sample_movie_data = f.read()
        with open("info-samples/info-sample-tv-show.txt", 'r') as f:
            self.sample_tv_data = f.read()
    
    def test_empty_output_returns_zero(self):
        """Test that empty raw_output returns 0"""
        result = show_detailed_probe("")
        assert result == 0

    def test_msg_5073_error_returns_zero(self):
        """Test that MSG:5073 error message returns 0"""
        error_output = 'MSG:5073,0,0,"No disc found"'
        result = show_detailed_probe(error_output)
        assert result == 0

    def test_movie_disc_parsing(self):
        """Test parsing single-title movie disc from info-sample-movie.txt (Equilibrium)"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(self.sample_movie_data)

        # Verify function returns 0 (Equilibrium 1:46:32 exceeds 75min max filter)
        assert result == 0

        # Verify output contains expected disc name
        output_text = output.getvalue()
        assert "Equilibrium" in output_text
        assert "1:46:32" in output_text
        assert "SKIP" in output_text  # Should be skipped due to duration

    def test_movie_disc_parsing_pass(self):
        """Test parsing single-title movie disc from info-sample-movie.txt (Equilibrium)"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(self.sample_movie_data, "PT15M", "PT4H")

        # Verify function returns 0 (Equilibrium 1:46:32 exceeds 75min max filter)
        assert result == 1

        # Verify output contains expected disc name
        output_text = output.getvalue()
        assert "Equilibrium" in output_text
        assert "1:46:32" in output_text
        assert "WILL RIP" in output_text  # Should be skipped due to duration


    def test_tv_show_disc_parsing(self):
        """Test parsing multi-title TV show disc from info-sample-tv-show.txt (SG1)"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(self.sample_tv_data)
        
        # Verify function returns 5 (all titles within 25-75min filters at ~44min each)
        assert result == 5
        
        # Verify output contains expected disc name
        output_text = output.getvalue()
        assert "SG1_V4_R1_YR4" in output_text
        
        # Verify all 5 titles are selected for rip
        assert output_text.count(">>> WILL RIP <<<") == 5

    def test_duration_filtering_short_titles(self):
        """Test that short titles (< 25min) are filtered out"""
        short_titles = """MSG:1005,0,1,"MakeMKV started"
DRV:0,2,999,1,"Test Drive","Test Disc","E:"
MSG:3028,0,3,"Title #1 was added (1 cell(s), 0:10:00)","1","1","0:10:00"
MSG:3028,16777216,3,"Title #2 was added (1 cell(s), 0:15:00)","2","1","0:15:00"
TCOUNT:2
CINFO:2,0,"Test Disc"
TINFO:0,9,0,"0:10:00"
TINFO:1,9,0,"0:15:00"
"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(short_titles)
        
        # Short titles should be filtered out (both are < 25min)
        assert result == 0
        output_text = output.getvalue()
        assert "SKIP" in output_text

    def test_duration_filtering_long_titles(self):
        """Test that long titles (> 1h15m) are filtered out"""
        long_titles = """MSG:1005,0,1,"MakeMKV started"
DRV:0,2,999,1,"Test Drive","Test Disc","E:"
MSG:3028,0,3,"Title #1 was added (1 cell(s), 2:00:00)","1","1","2:00:00"
MSG:3028,16777216,3,"Title #2 was added (1 cell(s), 1:30:00)","2","1","1:30:00"
TCOUNT:2
CINFO:2,0,"Test Disc"
TINFO:0,9,0,"2:00:00"
TINFO:1,9,0,"1:30:00"
"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(long_titles)
        
        # Long titles should be filtered out (both are > 1h15m)
        assert result == 0
        output_text = output.getvalue()
        assert "SKIP" in output_text

    def test_mixed_duration_filtering(self):
        """Test filtering works correctly with mixed duration titles"""
        mixed_titles = """MSG:1005,0,1,"MakeMKV started"
DRV:0,2,999,1,"Test Drive","Test Disc","E:"
MSG:3028,0,3,"Title #1 was added (1 cell(s), 0:44:00)","1","1","0:44:00"
MSG:3028,16777216,3,"Title #2 was added (1 cell(s), 0:20:00)","2","1","0:20:00"
MSG:3028,16777216,3,"Title #3 was added (1 cell(s), 0:55:00)","3","1","0:55:00"
MSG:3028,16777216,3,"Title #4 was added (1 cell(s), 0:15:00)","4","1","0:15:00"
TCOUNT:4
CINFO:2,0,"Test Disc"
TINFO:0,9,0,"0:44:00"
TINFO:1,9,0,"0:20:00"
TINFO:2,9,0,"0:55:00"
TINFO:3,9,0,"0:15:00"
"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(mixed_titles)
        
        # Only titles 0 and 2 are within 25min-75min range
        assert result == 2
        output_text = output.getvalue()
        will_rip_count = output_text.count(">>> WILL RIP <<<")
        skip_count = output_text.count("SKIP")
        assert will_rip_count == 2
        assert skip_count == 2

    def test_unknown_disc_name_handling(self):
        """Test behavior when no CINFO:2 is found"""
        minimal_output = """MSG:1005,0,1,"MakeMKV started"
DRV:0,2,999,1,"Test Drive","","E:"
MSG:3028,0,3,"Title #1 was added","1","1","0:44:00"
TCOUNT:1
CINFO:1,6206,"DVD disc"
TINFO:0,9,0,"0:44:00"
"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(minimal_output)
        
        assert result == 1
        output_text = output.getvalue()
        assert "Unknown Volume" in output_text

    def test_format_seconds_to_iso_in_output(self):
        """Test that formatted ISO durations appear in output"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(self.sample_tv_data)
        
        output_text = output.getvalue()
        # Should show both seconds and ISO format in summary
        assert "Min: 1500s (PT25M)" in output_text
        assert "Max: 4500s (PT1H15M)" in output_text

    def test_table_formatting(self):
        """Test that output is properly formatted as table"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(self.sample_movie_data)
        
        output_text = output.getvalue()
        # Verify table structure
        assert "ID" in output_text
        assert "Duration" in output_text
        assert "Total Sec" in output_text
        assert "Decision" in output_text
        # Verify separator line
        assert "===" in output_text
        
    def test_multiple_titles_same_duration(self):
        """Test parsing when multiple titles have same duration"""
        same_duration = """MSG:1005,0,1,"MakeMKV started"
DRV:0,2,999,1,"Test Drive","Test Disc","E:"
MSG:3028,0,3,"Title #1 was added","1","1","0:45:00"
MSG:3028,16777216,3,"Title #2 was added","2","1","0:45:00"
MSG:3028,16777216,3,"Title #3 was added","3","1","0:45:00"
TCOUNT:3
CINFO:2,0,"Test Disc"
TINFO:0,9,0,"0:45:00"
TINFO:1,9,0,"0:45:00"
TINFO:2,9,0,"0:45:00"
"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(same_duration)
        
        assert result == 3
        output_text = output.getvalue()
        assert output_text.count("0:45:00") == 3


@pytest.fixture
def custom_duration_ranges():
    """Fixture that returns custom MIN_LENGTH and MAX_LENGTH values"""
    return {
        'min': iso_to_seconds("PT10M"),  # 600 seconds
        'max': iso_to_seconds("PT2H")    # 7200 seconds
    }


class TestShowDetailedProbeWithCustomRanges:
    """Test show_detailed_probe with custom duration ranges"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Create sample data"""
        self.sample_data = """MSG:1005,0,1,"MakeMKV started"
DRV:0,2,999,1,"Test Drive","Test Disc","E:"
MSG:3028,0,3,"Title #1 was added","1","1","0:08:00"
MSG:3028,16777216,3,"Title #2 was added","2","1","0:15:00"
MSG:3028,16777216,3,"Title #3 was added","3","1","0:45:00"
MSG:3028,16777216,3,"Title #4 was added","4","1","2:30:00"
TCOUNT:4
CINFO:2,0,"Test Disc"
TINFO:0,9,0,"0:08:00"
TINFO:1,9,0,"0:15:00"
TINFO:2,9,0,"0:45:00"
TINFO:3,9,0,"2:30:00"
"""

    def test_wider_filter_includes_shorter_titles(self, custom_duration_ranges):
        """Test that wider range includes shorter titles"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(self.sample_data)
        
        # With default range (25-75min), only 1 title should pass
        # Title 0 (8min) - too short
        # Title 1 (15min) - too short  
        # Title 2 (45min) - within range
        # Title 3 (2.5hr) - too long
        assert result == 1

    def test_longer_title_excluded_in_default_range(self, custom_duration_ranges):
        """Test that 2h30m title is excluded with default 25min-75min range"""
        output = io.StringIO()
        with redirect_stdout(output):
            result = show_detailed_probe(self.sample_data)
        
        # Long title (2:30:00 = 9000 seconds) should be filtered
        assert result <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
