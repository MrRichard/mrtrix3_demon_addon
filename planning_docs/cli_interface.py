"""
Command-line interface for DWI Pipeline

This module provides the CLI entry point for the containerized
DWI processing pipeline with support for threading control.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
import logging

from dwi_pipeline.domain.enums import Species
from dwi_pipeline.application.factories import WorkflowFactory
from dwi_pipeline.infrastructure.bids import BidsReader
from dwi_pipeline.domain.validation import BidsValidator, FreeSurferValidator


def create_parser() -> argparse.ArgumentParser:
    """
    Create command-line argument parser.
    
    Returns:
        Configured ArgumentParser instance
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
  
  # Force rerun all steps
  dwi-pipeline sub-01 ses-01 --rerun
  
  # With specific working directory
  dwi-pipeline sub-01 ses-01 --work-dir /tmp/work
  
  # NHP processing (future)
  dwi-pipeline sub-NHP01 ses-01 --species nhp

Container Mounts:
  /data          - BIDS dataset (read-only)
  /freesurfer    - FreeSurfer derivatives (read-only)
  /out           - Output directory (read-write)
  
Expected Directory Structure:
  /data/
    sub-01/
      ses-01/
        dwi/
          sub-01_ses-01_dir-AP_dwi.nii.gz
          sub-01_ses-01_dir-AP_dwi.bval
          sub-01_ses-01_dir-AP_dwi.bvec
          sub-01_ses-01_dir-AP_dwi.json  (REQUIRED - contains TRT, PE direction)
        anat/
          sub-01_ses-01_T1w.nii.gz
  
  /freesurfer/
    sub-01/
      [ses-01/]  (optional session subdirectory)
        mri/
          aparc+aseg.mgz        (REQUIRED)
          brain.mgz             (REQUIRED)
          aparc.a2009s+aseg.mgz (recommended)

Output Structure:
  /out/
    sub-01/
      ses-01/
        dwi/
          *_connectome.csv      (Primary outputs)
          *_tractography.tck    (Tractography)
          *_metrics.json        (Summary metrics)
          *_qc-report.html      (QC visualization)
"""
    )
    
    # Required positional arguments
    parser.add_argument(
        'subject',
        type=str,
        help='Subject ID (e.g., sub-01)'
    )
    
    parser.add_argument(
        'session',
        type=str,
        help='Session ID (e.g., ses-01)'
    )
    
    # Processing options
    processing_group = parser.add_argument_group('Processing Options')
    
    processing_group.add_argument(
        '--n-threads',
        type=int,
        default=4,
        metavar='N',
        help='Number of threads for parallel processing (default: 4, max recommended: 32)'
    )
    
    processing_group.add_argument(
        '--species',
        type=str,
        choices=['human', 'nhp'],
        default='human',
        help='Species being processed (default: human). NHP support coming soon.'
    )
    
    processing_group.add_argument(
        '--rerun',
        action='store_true',
        help='Force rerun all steps (ignore cached outputs)'
    )
    
    # Directory options (defaults assume container mounts)
    directory_group = parser.add_argument_group('Directory Options')
    
    directory_group.add_argument(
        '--bids-dir',
        type=Path,
        default=Path('/data'),
        help='BIDS dataset directory (default: /data)'
    )
    
    directory_group.add_argument(
        '--freesurfer-dir',
        type=Path,
        default=Path('/freesurfer'),
        help='FreeSurfer derivatives directory (default: /freesurfer)'
    )
    
    directory_group.add_argument(
        '--output-dir',
        type=Path,
        default=Path('/out'),
        help='Output directory (default: /out)'
    )
    
    directory_group.add_argument(
        '--work-dir',
        type=Path,
        default=None,
        help='Working directory for intermediate files (default: /tmp/dwi_pipeline_work)'
    )
    
    # Advanced options
    advanced_group = parser.add_argument_group('Advanced Options')
    
    advanced_group.add_argument(
        '--plugin',
        type=str,
        choices=['Linear', 'MultiProc', 'SGE', 'PBS'],
        default='MultiProc',
        help='Nipype execution plugin (default: MultiProc)'
    )
    
    advanced_group.add_argument(
        '--verbose',
        '-v',
        action='count',
        default=0,
        help='Increase verbosity (can be repeated: -v, -vv, -vvv)'
    )
    
    advanced_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Build workflow but do not execute'
    )
    
    return parser


def configure_logging(verbosity: int) -> None:
    """
    Configure logging based on verbosity level.
    
    Args:
        verbosity: Verbosity count (0=WARNING, 1=INFO, 2=DEBUG, 3+=DEBUG with workflow details)
    """
    if verbosity == 0:
        level = logging.WARNING
    elif verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set Nipype logging
    if verbosity >= 3:
        from nipype import config
        config.enable_debug_mode()
        logging.getLogger('nipype.workflow').setLevel(logging.DEBUG)
        logging.getLogger('nipype.utils').setLevel(logging.DEBUG)


def validate_thread_count(n_threads: int) -> int:
    """
    Validate and adjust thread count.
    
    Args:
        n_threads: Requested thread count
        
    Returns:
        Validated thread count
    """
    if n_threads < 1:
        logging.warning(f"Invalid thread count {n_threads}, setting to 1")
        return 1
    
    if n_threads > 32:
        logging.warning(f"Thread count {n_threads} exceeds recommended maximum (32), proceeding anyway")
    
    return n_threads


def main() -> int:
    """
    Main entry point for the DWI pipeline.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # Configure logging
    configure_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 70)
    logger.info("MRtrix3 DWI Connectome Pipeline")
    logger.info("=" * 70)
    logger.info(f"Subject: {args.subject}")
    logger.info(f"Session: {args.session}")
    logger.info(f"Species: {args.species}")
    logger.info(f"Threads: {args.n_threads}")
    
    # Validate inputs exist
    if not args.bids_dir.exists():
        logger.error(f"BIDS directory not found: {args.bids_dir}")
        logger.error("Ensure /data is mounted correctly in the container")
        return 1
    
    if not args.freesurfer_dir.exists():
        logger.error(f"FreeSurfer directory not found: {args.freesurfer_dir}")
        logger.error("Ensure /freesurfer is mounted correctly in the container")
        return 1
    
    # Set working directory
    if args.work_dir is None:
        args.work_dir = Path('/tmp/dwi_pipeline_work')
    
    args.work_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Working directory: {args.work_dir}")
    
    # Validate thread count
    n_threads = validate_thread_count(args.n_threads)
    
    try:
        # Step 1: Discover BIDS files
        logger.info("\n" + "=" * 70)
        logger.info("STEP 1: BIDS File Discovery")
        logger.info("=" * 70)
        
        bids_reader = BidsReader(args.bids_dir)
        layout = bids_reader.discover(
            subject=args.subject,
            session=args.session
        )
        
        logger.info(f"✓ Found DWI data: {layout.dwi_ap.name}")
        logger.info(f"✓ Found anatomical: {layout.t1w.name}")
        logger.info(f"✓ Shell configuration: {layout.shell_config}")
        logger.info(f"✓ Distortion correction: {layout.distortion_correction}")
        
        # Step 2: Validate inputs
        logger.info("\n" + "=" * 70)
        logger.info("STEP 2: Input Validation")
        logger.info("=" * 70)
        
        # BIDS validation
        bids_validator = BidsValidator()
        is_valid, errors = bids_validator.validate(layout)
        
        if not is_valid:
            logger.error("BIDS validation failed:")
            for error in errors:
                logger.error(f"  ✗ {error}")
            return 1
        
        logger.info("✓ BIDS validation passed")
        
        # FreeSurfer validation (MANDATORY)
        fs_validator = FreeSurferValidator(args.freesurfer_dir)
        fs_valid, fs_errors = fs_validator.validate(
            subject=args.subject,
            session=args.session
        )
        
        if not fs_valid:
            logger.error("\n" + "!" * 70)
            logger.error("FREESURFER VALIDATION FAILED")
            logger.error("!" * 70)
            logger.error("FreeSurfer recon-all is REQUIRED for this pipeline.")
            logger.error("\nErrors found:")
            for error in fs_errors:
                logger.error(f"  ✗ {error}")
            logger.error("\nPlease ensure FreeSurfer recon-all has completed successfully.")
            logger.error("Expected location: {}/{}[/{}]/mri/".format(
                args.freesurfer_dir, args.subject, args.session if args.session else ""
            ))
            return 1
        
        logger.info("✓ FreeSurfer validation passed")
        logger.info(f"  FreeSurfer directory: {layout.freesurfer_dir}")
        
        # Step 3: Create processing configuration
        logger.info("\n" + "=" * 70)
        logger.info("STEP 3: Processing Configuration")
        logger.info("=" * 70)
        
        from dwi_pipeline.domain.models import ProcessingConfig
        
        config = ProcessingConfig(
            subject=args.subject,
            session=args.session,
            species=Species(args.species),
            output_dir=args.output_dir / args.subject / args.session / 'dwi',
            work_dir=args.work_dir,
            n_threads=n_threads,
            rerun=args.rerun
        )
        
        # Create output directory
        config.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✓ Configuration created")
        logger.info(f"  Output: {config.output_dir}")
        logger.info(f"  Threads: {config.n_threads}")
        logger.info(f"  Rerun: {config.rerun}")
        
        # Step 4: Build workflow
        logger.info("\n" + "=" * 70)
        logger.info("STEP 4: Workflow Construction")
        logger.info("=" * 70)
        
        factory = WorkflowFactory()
        workflow = factory.create_workflow(layout, config)
        
        logger.info(f"✓ Workflow constructed")
        logger.info(f"  Name: {workflow.name}")
        logger.info(f"  Nodes: {len(workflow.list_node_names())}")
        
        if args.dry_run:
            logger.info("\n" + "=" * 70)
            logger.info("DRY RUN - Workflow construction complete")
            logger.info("=" * 70)
            logger.info("Workflow would execute the following nodes:")
            for node_name in workflow.list_node_names():
                logger.info(f"  • {node_name}")
            return 0
        
        # Step 5: Execute workflow
        logger.info("\n" + "=" * 70)
        logger.info("STEP 5: Workflow Execution")
        logger.info("=" * 70)
        logger.info(f"Starting execution with {n_threads} threads...")
        logger.info("This may take several hours depending on data size.")
        
        plugin_args = {}
        if args.plugin == 'MultiProc':
            plugin_args['n_procs'] = n_threads
        
        workflow.run(
            plugin=args.plugin,
            plugin_args=plugin_args
        )
        
        logger.info("✓ Workflow execution completed successfully")
        
        # Step 6: Generate report
        logger.info("\n" + "=" * 70)
        logger.info("STEP 6: QC Report Generation")
        logger.info("=" * 70)
        
        from dwi_pipeline.infrastructure.reporting import QCReportGenerator
        
        reporter = QCReportGenerator()
        report_path = reporter.generate(
            subject=args.subject,
            session=args.session,
            output_dir=config.output_dir
        )
        
        logger.info(f"✓ QC report generated: {report_path}")
        
        # Success summary
        logger.info("\n" + "=" * 70)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info(f"Outputs available at: {config.output_dir}")
        logger.info("\nKey outputs:")
        logger.info(f"  • Connectomes: *_connectome.csv")
        logger.info(f"  • Tractography: *_tractography.tck")
        logger.info(f"  • QC Report: {report_path.name}")
        logger.info(f"  • Metrics: *_metrics.json")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Pipeline failed with error: {e}")
        logger.error("\nFor support, please check:")
        logger.error("  • BIDS data structure is correct")
        logger.error("  • FreeSurfer recon completed successfully")
        logger.error("  • All required JSON sidecars are present")
        logger.error("  • Container mounts are correct")
        return 1


if __name__ == '__main__':
    sys.exit(main())
