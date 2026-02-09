# DWI Pipeline Documentation

Welcome to the documentation for the DWI Pipeline, a containerized diffusion-weighted imaging processing pipeline that uses Nipype to orchestrate MRtrix3, FSL, and ANTs commands.

## Table of Contents

1. [Architecture](architecture.md) - System design and components
2. [User Guide](user_guide.md) - Installation, usage, and output interpretation
3. [Development Guide](development.md) - Contributing and extending the pipeline
4. [API Reference](api.md) - Detailed class and method documentation

## Overview

The DWI Pipeline processes BIDS-formatted diffusion-weighted imaging data into structural connectivity matrices. It implements a clean architecture with well-defined layers:

- **CLI Layer**: Command-line interface and argument parsing
- **Application Layer**: Workflow orchestration and strategy patterns
- **Domain Layer**: Core business logic and data models
- **Infrastructure Layer**: External tool wrappers and interfaces

The pipeline automatically detects processing parameters from your data, including shell configuration and distortion correction methods, and supports both single-shell and multi-shell DWI processing with human and non-human primate brains.