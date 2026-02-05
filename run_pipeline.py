#!/usr/bin/env python3
"""
MRtrix3 DWI Pipeline for BIDS-formatted data.

This script processes BIDS-formatted diffusion-weighted imaging data
to generate structural connectivity matrices using MRtrix3.

Usage:
    python run_pipeline.py --bids-dir /path/to/bids --subject sub-01 [options]

Example:
    python run_pipeline.py --bids-dir /data/bids --subject sub-01 --session ses-01 --human
"""

import argparse
import json
import os
import sys
from typing import Optional, List, Dict, Any, Tuple

from bids_discovery import (
    BIDSLayout,
    create_bids_layout,
    print_layout_summary,
    extract_fieldmap_parameters,
    detect_shell_configuration,
)
from SlurmBatch import SLURMFileCreator


def load_config(config_path: str) -> dict:
    """Load pipeline configuration from JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def load_commands(command_file: str) -> dict:
    """Load command definitions from JSON file."""
    with open(command_file, 'r') as f:
        return json.load(f)


def create_replacements(
    layout: BIDSLayout,
    config: dict,
    is_nhp: bool = False,
    external_mask: Optional[str] = None
) -> Dict[str, str]:
    """
    Create replacement dictionary for command templates.

    Args:
        layout: BIDSLayout with discovered file paths
        config: Pipeline configuration
        is_nhp: Whether processing non-human primate data
        external_mask: Optional path to external brain mask

    Returns:
        Dictionary mapping placeholder names to actual values
    """
    replacements = {
        # BIDS DWI files
        "DWI_AP": layout.dwi_ap or "",
        "DWI_AP_BVEC": layout.dwi_ap_bvec or "",
        "DWI_AP_BVAL": layout.dwi_ap_bval or "",
        "DWI_PA": layout.dwi_pa or "",
        "DWI_PA_BVEC": layout.dwi_pa_bvec or "",
        "DWI_PA_BVAL": layout.dwi_pa_bval or "",

        # Anatomical
        "ANAT": layout.t1w or "",

        # Directories
        "OUTPUT": layout.output_dir or "",
        "TEMPLATE": config.get('templates', '/templates'),

        # DWI parameters
        "PE_DIR": layout.pe_direction or "j",
        "READOUTTIME": str(layout.total_readout_time or 0.1),

        # Fieldmap files
        "FIELDMAP_MAG1": layout.fmap_magnitude1 or "",
        "FIELDMAP_MAG2": layout.fmap_magnitude2 or "",
        "FIELDMAP_PHASEDIFF": layout.fmap_phasediff or "",

        # FreeSurfer paths
        "FREESURFER_DIR": layout.freesurfer_dir or "",
        "FS_APARC_ASEG": layout.fs_aparc_aseg or "",
        "FS_APARC_DK": layout.fs_aparc_dk or "",
        "FS_APARC_DESTRIEUX": layout.fs_aparc_destrieux or "",
        "FS_BRAIN": layout.fs_brain or "",
        "FS_VERSION": layout.freesurfer_version or "none",

        # External mask if provided
        "EXTERNAL_MASK": external_mask or "",

        # Processing config
        "SPECIES": "nhp" if is_nhp else "human",
        "SUBJECT_NAME": layout.subject,
    }

    # Calculate DELTA_TE for fieldmap correction
    if layout.fmap_phasediff_json and os.path.exists(layout.fmap_phasediff_json):
        fmap_params = extract_fieldmap_parameters({
            'phasediff': layout.fmap_phasediff,
            'phasediff_json': layout.fmap_phasediff_json
        })
        delta_te = fmap_params.get('delta_te')
        if delta_te:
            # Convert to milliseconds for fsl_prepare_fieldmap
            replacements["DELTA_TE"] = str(delta_te * 1000)
        else:
            replacements["DELTA_TE"] = "2.46"  # Default Siemens value
    else:
        replacements["DELTA_TE"] = "2.46"

    return replacements


def filter_steps(
    steps: List[dict],
    layout: BIDSLayout,
    replacements: Dict[str, str],
    is_nhp: bool = False,
    has_external_mask: bool = False
) -> Tuple[List[dict], List[str]]:
    """
    Filter pipeline steps based on available data and configuration.

    Args:
        steps: List of step definitions from command JSON
        layout: BIDSLayout with discovered files
        replacements: Replacement dictionary
        is_nhp: Whether processing non-human primate data
        has_external_mask: Whether an external mask was provided

    Returns:
        Tuple of (filtered_steps, skipped_step_reasons)
    """
    filtered = []
    skipped = []

    distortion_correction = layout.distortion_correction
    shell_config = layout.shell_config

    for step in steps:
        step_name = step['name']

        # Check species filter
        if 'species' in step:
            step_species = step['species']
            if step_species == 'human' and is_nhp:
                skipped.append(f"{step_name} (human only)")
                continue
            elif step_species == 'nhp' and not is_nhp:
                skipped.append(f"{step_name} (NHP only)")
                continue

        # Check distortion correction filter
        if 'distortion_correction' in step:
            step_dc = step['distortion_correction']
            if step_dc != distortion_correction:
                skipped.append(f"{step_name} (requires {step_dc} distortion correction)")
                continue

        # Check shell configuration filter
        if 'shell_config' in step:
            step_shell = step['shell_config']
            if step_shell != shell_config:
                skipped.append(f"{step_name} (requires {step_shell})")
                continue

        # Check conditional execution
        if 'conditional' in step:
            condition = step['conditional']
            if condition == 'skip_if_external_mask' and has_external_mask:
                skipped.append(f"{step_name} (using external mask)")
                continue

        # Check requires field (FreeSurfer files)
        if 'requires' in step:
            required = step['requires']
            if required not in replacements or not replacements[required]:
                skipped.append(f"{step_name} (missing {required})")
                continue

        filtered.append(step)

    return filtered, skipped


def apply_replacements(text: str, replacements: Dict[str, str]) -> str:
    """Apply all replacements to a text string."""
    result = text
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def build_commands(
    steps: List[dict],
    replacements: Dict[str, str],
    output_dir: str,
    rerun: bool = False
) -> List[str]:
    """
    Build shell commands from step definitions.

    Args:
        steps: List of filtered step definitions
        replacements: Replacement dictionary
        output_dir: Output directory path
        rerun: If True, always run steps (skip output checks)

    Returns:
        List of shell command strings
    """
    commands = []

    for step in steps:
        step_name = step['name']
        cmd = apply_replacements(step['cmd'], replacements)
        validation_output = apply_replacements(step['validation_output'], replacements)

        log_file = os.path.join(output_dir, f"{step_name}_log.txt")
        command_with_logging = f"{cmd} > {log_file} 2>&1"

        if rerun:
            commands.append(command_with_logging)
        else:
            # Wrap in conditional to skip if output exists
            commands.append(f'if [ ! -f {validation_output} ]; then\n  {command_with_logging}\nfi')

    return commands


def create_bash_script(commands: List[str], output_file: str) -> str:
    """
    Create a bash script with all commands.

    Args:
        commands: List of shell commands
        output_file: Path to write the script

    Returns:
        Path to the created script
    """
    with open(output_file, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("\n# MRtrix3 DWI Pipeline - Generated Script\n")
        f.write("# This script was automatically generated by run_pipeline.py\n\n")

        # Environment setup
        f.write("# Set up environment variables for MRtrix3 and FreeSurfer\n")
        f.write("if [ -d '/opt/mrtrix3' ]; then\n")
        f.write("    export MRTRIX3_DIR='/opt/mrtrix3'\n")
        f.write("elif [ -d '/usr/local/mrtrix3' ]; then\n")
        f.write("    export MRTRIX3_DIR='/usr/local/mrtrix3'\n")
        f.write("elif [ -d '/mrtrix3' ]; then\n")
        f.write("    export MRTRIX3_DIR='/mrtrix3'\n")
        f.write("else\n")
        f.write("    echo 'WARNING: MRtrix3 directory not found, using default'\n")
        f.write("    export MRTRIX3_DIR='/opt/mrtrix3'\n")
        f.write("fi\n\n")

        f.write("if [ -d '/opt/freesurfer' ]; then\n")
        f.write("    export FREESURFER_HOME='/opt/freesurfer'\n")
        f.write("elif [ -d '/usr/local/freesurfer' ]; then\n")
        f.write("    export FREESURFER_HOME='/usr/local/freesurfer'\n")
        f.write("elif [ -d '/freesurfer' ]; then\n")
        f.write("    export FREESURFER_HOME='/freesurfer'\n")
        f.write("else\n")
        f.write("    echo 'WARNING: FreeSurfer directory not found'\n")
        f.write("    export FREESURFER_HOME='/opt/freesurfer'\n")
        f.write("fi\n\n")

        f.write("echo \"Using MRTRIX3_DIR: $MRTRIX3_DIR\"\n")
        f.write("echo \"Using FREESURFER_HOME: $FREESURFER_HOME\"\n\n")

        f.write("# Verify critical files exist\n")
        f.write("echo 'Checking MRtrix3 label conversion files...'\n")
        f.write('ls -la "$MRTRIX3_DIR/share/mrtrix3/labelconvert/fs_default.txt" 2>/dev/null || echo \'fs_default.txt not found\'\n')
        f.write('ls -la "$MRTRIX3_DIR/share/mrtrix3/labelconvert/fs_a2009s.txt" 2>/dev/null || echo \'fs_a2009s.txt not found\'\n\n')

        # Write commands
        f.write("# Pipeline commands\n")
        for command in commands:
            f.write(command)
            f.write("\n\n")

    os.chmod(output_file, 0o755)
    return output_file


def add_mask_commands(
    commands: List[str],
    external_mask: str,
    output_dir: str
) -> List[str]:
    """
    Add commands to copy and convert an external mask.

    Args:
        commands: Existing command list
        external_mask: Path to external mask file
        output_dir: Output directory

    Returns:
        Updated command list with mask commands inserted
    """
    mask_commands = [
        f"# Copy and convert external brain mask",
        f"if [ ! -f {output_dir}/mask.nii.gz ]; then",
        f"  cp {external_mask} {output_dir}/mask.nii.gz > {output_dir}/copy_external_mask_log.txt 2>&1",
        f"fi",
        f"if [ ! -f {output_dir}/mask.mif ]; then",
        f"  mrconvert {output_dir}/mask.nii.gz {output_dir}/mask.mif -force > {output_dir}/convert_external_mask_log.txt 2>&1",
        f"fi"
    ]

    # Find insertion point (after bias correction step)
    insert_index = 0
    for i, cmd in enumerate(commands):
        if 'dwibiascorrect' in cmd:
            insert_index = i + 1
            break

    for i, mask_cmd in enumerate(mask_commands):
        commands.insert(insert_index + i, mask_cmd)

    return commands


def add_reporting_command(
    commands: List[str],
    subject: str,
    output_dir: str,
    is_nhp: bool,
    fs_version: str
) -> List[str]:
    """Add the final reporting command to the pipeline."""
    species_flag = 'nhp' if is_nhp else 'human'

    reporting_cmd = f"""
# Generate standardized report
python3 /scripts/generate_standardized_report.py \\
    --subject {subject} \\
    --output_dir {output_dir} \\
    --species {species_flag} \\
    --freesurfer_version {fs_version} \\
    > {output_dir}/reporting_log.txt 2>&1
"""
    commands.append(reporting_cmd)
    return commands


def create_skull_strip_command(t1w_path: str, is_nhp: bool) -> Optional[str]:
    """Create skull stripping command for NHP processing."""
    if not is_nhp:
        return None

    model_path = "/UNet_Model/models/Site-All-T-epoch_36.model"
    output_dir = os.path.dirname(t1w_path)
    return f"python3 /UNet_Model/muSkullStrip.py -in {t1w_path} -model {model_path} -out {output_dir}"


def main():
    """Main entry point for the BIDS DWI pipeline."""
    parser = argparse.ArgumentParser(
        description='MRtrix3 DWI Pipeline for BIDS-formatted data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python run_pipeline.py --bids-dir /data/bids --subject sub-01 --human

  # With session and custom output
  python run_pipeline.py --bids-dir /data/bids --subject sub-01 --session ses-01 \\
      --output-dir /data/derivatives/mrtrix3/sub-01/ses-01

  # Dry run to see what would be executed
  python run_pipeline.py --bids-dir /data/bids --subject sub-01 --dry-run

  # With external brain mask
  python run_pipeline.py --bids-dir /data/bids --subject sub-01 --mask /path/to/mask.nii.gz
"""
    )

    # Required arguments
    parser.add_argument('--bids-dir', type=str, required=True,
                        help='Path to BIDS root directory')
    parser.add_argument('--subject', type=str, required=True,
                        help='Subject ID (e.g., sub-01)')

    # Optional arguments
    parser.add_argument('--session', type=str, default=None,
                        help='Session ID (e.g., ses-01)')
    parser.add_argument('--config', type=str, default='config.json',
                        help='Path to config JSON file (default: config.json)')
    parser.add_argument('--command-file', type=str, default='enhanced_commands_bids.json',
                        help='Path to command JSON file (default: enhanced_commands_bids.json)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory (default: derivatives/mrtrix3/sub-XX/)')
    parser.add_argument('--mask', type=str, default=None,
                        help='Path to external brain mask (skips dwi2mask step)')

    # Species selection
    species_group = parser.add_mutually_exclusive_group()
    species_group.add_argument('--human', dest='human', action='store_true',
                               help='Process as human data (default)')
    species_group.add_argument('--nhp', dest='nhp', action='store_true',
                               help='Process as non-human primate data')

    # Processing options
    parser.add_argument('--rerun', action='store_true',
                        help='Force rerun of all steps (ignore existing outputs)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Generate scripts without submitting to SLURM')

    args = parser.parse_args()

    # Default to human if neither specified
    if not args.nhp and not args.human:
        args.human = True
    is_nhp = args.nhp

    print("=" * 60)
    print("MRtrix3 DWI Pipeline - BIDS Processing")
    print("=" * 60)
    print(f"Subject: {args.subject}")
    print(f"Species: {'Non-Human Primate' if is_nhp else 'Human'}")
    print(f"BIDS Directory: {args.bids_dir}")
    if args.session:
        print(f"Session: {args.session}")

    # Validate BIDS directory exists
    if not os.path.exists(args.bids_dir):
        print(f"ERROR: BIDS directory not found: {args.bids_dir}")
        sys.exit(1)

    # Load configuration
    print("\n=== LOADING CONFIGURATION ===")
    script_dir = os.path.dirname(os.path.abspath(__file__))

    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(script_dir, config_path)

    if not os.path.exists(config_path):
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)
    print(f"Loaded config from: {config_path}")

    command_file = args.command_file
    if not os.path.isabs(command_file):
        command_file = os.path.join(script_dir, command_file)

    if not os.path.exists(command_file):
        print(f"ERROR: Command file not found: {command_file}")
        sys.exit(1)

    command_data = load_commands(command_file)
    print(f"Loaded commands from: {command_file}")

    # Discover BIDS files
    print("\n=== BIDS FILE DISCOVERY ===")
    layout = create_bids_layout(
        bids_dir=args.bids_dir,
        subject=args.subject,
        session=args.session,
        output_dir=args.output_dir
    )

    # Validate layout
    is_valid, errors = layout.validate()
    if not is_valid:
        print("ERROR: BIDS validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print_layout_summary(layout)

    # Create output directory
    if not os.path.exists(layout.output_dir):
        os.makedirs(layout.output_dir)
        print(f"\nCreated output directory: {layout.output_dir}")

    # Validate external mask if provided
    has_external_mask = False
    if args.mask:
        if not os.path.exists(args.mask):
            print(f"ERROR: External mask not found: {args.mask}")
            sys.exit(1)
        has_external_mask = True
        print(f"\nUsing external brain mask: {args.mask}")

    # Create replacements
    print("\n=== BUILDING REPLACEMENTS ===")
    replacements = create_replacements(layout, config, is_nhp, args.mask)

    # Filter steps
    print("\n=== FILTERING PIPELINE STEPS ===")
    filtered_steps, skipped_reasons = filter_steps(
        steps=command_data['steps'],
        layout=layout,
        replacements=replacements,
        is_nhp=is_nhp,
        has_external_mask=has_external_mask
    )

    print(f"Included steps: {len(filtered_steps)}")
    for step in filtered_steps:
        print(f"  + {step['name']}")

    if skipped_reasons:
        print(f"\nSkipped steps: {len(skipped_reasons)}")
        for reason in skipped_reasons:
            print(f"  - {reason}")

    # Build commands
    print("\n=== BUILDING COMMANDS ===")
    commands = build_commands(
        steps=filtered_steps,
        replacements=replacements,
        output_dir=layout.output_dir,
        rerun=args.rerun
    )

    # Add external mask handling
    if has_external_mask:
        commands = add_mask_commands(commands, args.mask, layout.output_dir)

    # Add reporting command
    fs_version = layout.freesurfer_version or 'none'
    commands = add_reporting_command(
        commands=commands,
        subject=args.subject,
        output_dir=layout.output_dir,
        is_nhp=is_nhp,
        fs_version=fs_version
    )

    print(f"Total commands: {len(commands)}")

    # Create bash script
    print("\n=== CREATING BATCH SCRIPT ===")
    script_name = f"{args.subject}_pipeline.sh"
    if args.session:
        script_name = f"{args.subject}_{args.session}_pipeline.sh"

    batch_script = create_bash_script(
        commands=commands,
        output_file=os.path.join(layout.output_dir, script_name)
    )
    print(f"Created script: {batch_script}")

    # Create SLURM batch file
    slurm_creator = SLURMFileCreator(args.subject, config)
    slurm_creator.create_bind_string(args.bids_dir, layout.output_dir)

    skull_strip_cmd = create_skull_strip_command(layout.t1w, is_nhp)
    slurm_creator.create_batch_file(batch_script, is_nhp, skull_strip_cmd or '')

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE PREPARATION COMPLETE")
    print("=" * 60)
    print(f"Subject: {args.subject}")
    print(f"Species: {'NHP' if is_nhp else 'Human'}")
    print(f"Shell configuration: {layout.shell_config}")
    print(f"Distortion correction: {layout.distortion_correction}")
    print(f"FreeSurfer: {fs_version}")
    print(f"Output directory: {layout.output_dir}")
    print(f"Batch script: {batch_script}")

    if args.dry_run:
        print("\n[DRY RUN] Scripts generated but not submitted to SLURM")
    else:
        print("\nReady for SLURM submission!")
        print(f"Submit with: sbatch jobs/{args.subject}.slurm")


if __name__ == "__main__":
    main()
