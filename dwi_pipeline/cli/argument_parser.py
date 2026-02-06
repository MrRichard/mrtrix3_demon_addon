import argparse
from pathlib import Path

def create_parser() -> argparse.ArgumentParser:
    """
    Create command-line argument parser for the DWI pipeline.
    """
    parser = argparse.ArgumentParser(
        prog='dwi-pipeline',
        description='MRtrix3 DWI Connectome Pipeline (Container Version)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (human, auto-detect shell type)
  dwi-pipeline sub-01 ses-01
  
  # With custom thread count
  dwi-pipeline sub-01 ses-01 --n-threads 16
"""
    )
    
    # Required positional arguments
    parser.add_argument('subject', type=str, help='Subject ID (e.g., 01)')
    parser.add_argument('session', type=str, help='Session ID (e.g., 01)')
    
    # Processing options
    processing_group = parser.add_argument_group('Processing Options')
    processing_group.add_argument('--n-threads', type=int, default=4, metavar='N', help='Number of threads (default: 4)')
    processing_group.add_argument('--species', type=str, choices=['human', 'nhp'], default='human', help='Species (default: human)')
    processing_group.add_argument('--rerun', action='store_true', help='Force rerun all steps')
    
    # Directory options
    directory_group = parser.add_argument_group('Directory Options')
    directory_group.add_argument('--bids-dir', type=Path, default=Path('/data'), help='BIDS dataset directory (default: /data)')
    directory_group.add_argument('--freesurfer-dir', type=Path, default=Path('/freesurfer'), help='FreeSurfer derivatives directory (default: /freesurfer)')
    directory_group.add_argument('--output-dir', type=Path, default=Path('/out'), help='Output directory (default: /out)')
    directory_group.add_argument('--work-dir', type=Path, default=Path('/tmp/work'), help='Working directory for intermediate files (default: /tmp/work)')

    # Advanced options
    advanced_group = parser.add_argument_group('Advanced Options')
    advanced_group.add_argument('--verbose', '-v', action='count', default=0, help='Increase verbosity')
    
    return parser
