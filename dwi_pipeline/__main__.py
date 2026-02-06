import sys
import logging
from .cli.argument_parser import create_parser
from .infrastructure.bids.reader import BidsReader
from .infrastructure.bids.metadata import BidsMetadataExtractor
from .infrastructure.freesurfer.parcellation import FreeSurferValidator
from .domain.models.processing_config import ProcessingConfig
from .domain.enums.species import Species
from .application.factories.workflow_factory import WorkflowFactory

def configure_logging(verbosity: int):
    """Configures logging based on verbosity level."""
    log_level = logging.WARNING
    if verbosity == 1:
        log_level = logging.INFO
    elif verbosity >= 2:
        log_level = logging.DEBUG
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    """Main entry point for the DWI pipeline."""
    parser = create_parser()
    args = parser.parse_args()

    configure_logging(args.verbose)
    logger = logging.getLogger(__name__)

    try:
        logger.info("--- DWI Pipeline Start ---")

        # 1. Discover BIDS layout
        logger.info(f"Discovering BIDS data for sub-{args.subject}, ses-{args.session} in {args.bids_dir}")
        bids_reader = BidsReader(args.bids_dir, args.freesurfer_dir)
        layout = bids_reader.discover(args.subject, args.session)

        # 2. Validate FreeSurfer data
        logger.info("Validating FreeSurfer data...")
        fs_validator = FreeSurferValidator(args.freesurfer_dir)
        fs_valid, fs_errors = fs_validator.validate(args.subject, args.session)
        if not fs_valid:
            logger.error("FreeSurfer validation failed:")
            for error in fs_errors:
                logger.error(f"  - {error}")
            sys.exit(1)
        logger.info("FreeSurfer data found and valid.")

        # 3. Extract metadata and determine strategies
        logger.info("Extracting metadata...")
        metadata_extractor = BidsMetadataExtractor(layout)
        dwi_data = metadata_extractor.extract_dwi_metadata()
        layout.shell_config = dwi_data.shell_type
        layout.distortion_correction = metadata_extractor.determine_distortion_strategy(dwi_data)
        logger.info(f"Shell config: {layout.shell_config.value}")
        logger.info(f"Distortion correction: {layout.distortion_correction.value}")

        # 4. Create ProcessingConfig
        config = ProcessingConfig(
            subject=args.subject,
            session=args.session,
            output_dir=args.output_dir,
            work_dir=args.work_dir,
            n_threads=args.n_threads,
            species=Species(args.species),
            rerun=args.rerun,
            bids_dir=args.bids_dir,
            freesurfer_dir=args.freesurfer_dir
        )
        
        # 5. Create and run workflow
        logger.info("Creating workflow...")
        config.subject_output_dir.mkdir(parents=True, exist_ok=True)
        workflow_factory = WorkflowFactory()
        workflow = workflow_factory.create_workflow(layout, config, dwi_data)

        logger.info(f"Executing workflow: {workflow.name}")
        workflow.run(plugin='MultiProc', plugin_args={'n_procs': config.n_threads})
        
        logger.info("--- DWI Pipeline Finished Successfully ---")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
