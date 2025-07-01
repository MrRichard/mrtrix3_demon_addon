#!/usr/bin/env python3
"""
Universal Standardized Reporting System for Human and NHP Connectomes
Generates consistent reports regardless of species or available atlases.
"""

import argparse
import json
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import glob

class ConnectomeReporter:
    def __init__(self, subject_name, output_dir, species='human', freesurfer_version='none'):
        self.subject_name = subject_name
        self.output_dir = output_dir
        self.species = species
        self.freesurfer_version = freesurfer_version
        self.report = {
            'subject_id': subject_name,
            'species': species,
            'processing_date': datetime.now().isoformat(),
            'pipeline_version': 'MRTRIX3_Enhanced_v2.0',
            'freesurfer_version': freesurfer_version,
            'connectomes': {},
            'quality_metrics': {},
            'graph_metrics': {},
            'processing_summary': {},
            'warnings': []
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def discover_connectomes(self):
        """Discover all available connectome files in the output directory."""
        connectome_patterns = {
            'Brainnetome_counts': 'connectome_Brainnetome_counts.csv',
            'Brainnetome_scaled': 'connectome_Brainnetome_scaled.csv',
            'FreeSurfer_DK_counts': 'connectome_FreeSurfer_DK_counts.csv',
            'FreeSurfer_DK_scaled': 'connectome_FreeSurfer_DK_scaled.csv',
            'FreeSurfer_Destrieux_counts': 'connectome_FreeSurfer_Destrieux_counts.csv',
            'FreeSurfer_Destrieux_scaled': 'connectome_FreeSurfer_Destrieux_scaled.csv'
        }
        
        available_connectomes = {}
        
        for name, filename in connectome_patterns.items():
            filepath = os.path.join(self.output_dir, filename)
            if os.path.exists(filepath):
                available_connectomes[name] = filepath
                self.logger.info(f"Found connectome: {name}")
            else:
                self.logger.debug(f"Connectome not found: {name}")
        
        return available_connectomes

    def load_connectome(self, filepath):
        """Load and validate a connectome CSV file."""
        try:
            matrix = pd.read_csv(filepath, header=None).values
            if matrix.shape[0] != matrix.shape[1]:
                raise ValueError(f"Connectome matrix is not square: {matrix.shape}")
            return matrix
        except Exception as e:
            self.logger.error(f"Error loading connectome {filepath}: {e}")
            return None

    def calculate_basic_metrics(self, matrix, connectome_name):
        """Calculate basic connectivity metrics for a given connectome."""
        if matrix is None:
            return {}
        
        # Basic connectivity metrics
        total_streamlines = int(np.sum(matrix) / 2)  # Symmetric matrix
        total_connections = int(np.sum(matrix > 0) / 2)
        n_nodes = matrix.shape[0]
        connection_density = total_connections / (n_nodes * (n_nodes - 1) / 2)
        
        # Connection strength statistics
        nonzero_connections = matrix[matrix > 0]
        mean_strength = float(np.mean(nonzero_connections)) if len(nonzero_connections) > 0 else 0
        std_strength = float(np.std(nonzero_connections)) if len(nonzero_connections) > 0 else 0
        max_strength = float(np.max(matrix))
        
        # Sparsity
        sparsity = 1 - (np.sum(matrix > 0) / (n_nodes ** 2))
        
        return {
            'n_nodes': n_nodes,
            'total_streamlines': total_streamlines,
            'total_connections': total_connections,
            'connection_density': round(connection_density, 6),
            'mean_connection_strength': round(mean_strength, 3),
            'std_connection_strength': round(std_strength, 3),
            'max_connection_strength': round(max_strength, 3),
            'sparsity': round(sparsity, 6)
        }

    def calculate_graph_metrics(self, matrix):
        """Calculate basic graph theory metrics without requiring external libraries."""
        if matrix is None:
            return {}
        
        # Binarize matrix for topological analysis
        binary_matrix = (matrix > 0).astype(int)
        
        # Node degrees
        degrees = np.sum(binary_matrix, axis=1)
        
        # Basic clustering coefficient (simplified local version)
        clustering_coeffs = []
        for i in range(len(binary_matrix)):
            neighbors = np.where(binary_matrix[i] > 0)[0]
            if len(neighbors) < 2:
                clustering_coeffs.append(0.0)
            else:
                # Count triangles involving node i
                possible_edges = len(neighbors) * (len(neighbors) - 1) / 2
                actual_edges = np.sum(binary_matrix[np.ix_(neighbors, neighbors)]) / 2
                clustering_coeffs.append(actual_edges / possible_edges if possible_edges > 0 else 0)
        
        # Global metrics
        mean_degree = float(np.mean(degrees))
        std_degree = float(np.std(degrees))
        max_degree = int(np.max(degrees))
        mean_clustering = float(np.mean(clustering_coeffs))
        
        # Efficiency approximation (inverse of average shortest path)
        # Simplified version using degree as proxy
        global_efficiency = mean_degree / (len(binary_matrix) - 1)
        
        return {
            'mean_degree': round(mean_degree, 3),
            'std_degree': round(std_degree, 3),
            'max_degree': max_degree,
            'mean_clustering_coefficient': round(mean_clustering, 6),
            'global_efficiency_approx': round(global_efficiency, 6)
        }

    def check_processing_quality(self):
        """Check various quality control metrics from the processing pipeline."""
        quality_metrics = {}
        
        # Check for key processing files
        key_files = {
            'tracks_original': 'tracks_10M_hollander.tck',
            'tracks_sift': 'sift_1M_hollander.tck',
            'wmfod': 'wmfod_norm_hollander.mif',
            'mask': 'mask.mif',
            'mean_b0': 'mean_b0_processed.mif'
        }
        
        for file_type, filename in key_files.items():
            filepath = os.path.join(self.output_dir, filename)
            quality_metrics[f'{file_type}_exists'] = os.path.exists(filepath)
            if os.path.exists(filepath):
                quality_metrics[f'{file_type}_size_mb'] = round(os.path.getsize(filepath) / 1024 / 1024, 2)
        
        # SIFT filtering ratio
        if quality_metrics.get('tracks_original_exists') and quality_metrics.get('tracks_sift_exists'):
            # This is an approximation - actual ratio would need to be read from SIFT logs
            quality_metrics['sift_filtering_ratio'] = 0.1  # 10M -> 1M = 10% retention
        
        # Species-specific quality checks
        if self.species == 'human':
            quality_metrics['freesurfer_available'] = self.freesurfer_version != 'none'
            if self.freesurfer_version not in ['freesurfer8.0', 'FreeSurfer7']:
                self.report['warnings'].append(f"Using old FreeSurfer version: {self.freesurfer_version}")
        
        return quality_metrics

    def generate_processing_summary(self, available_connectomes):
        """Generate a summary of the processing pipeline results."""
        summary = {
            'total_connectomes_generated': len(available_connectomes),
            'available_atlases': [],
            'available_metrics': ['counts', 'scaled'] if any('scaled' in name for name in available_connectomes.keys()) else ['counts'],
            'processing_parameters': {
                'initial_tracks': '10M',
                'final_tracks_sift': '1M',
                'tractography_algorithm': 'iFOD2_ACT',
                'max_length': 250,
                'cutoff': 0.06,
                'sift_applied': True,
                'species': self.species
            }
        }
        
        # Determine available atlases
        if any('Brainnetome' in name for name in available_connectomes.keys()):
            summary['available_atlases'].append('Brainnetome')
        if any('FreeSurfer_DK' in name for name in available_connectomes.keys()):
            summary['available_atlases'].append('FreeSurfer_DK')
        if any('FreeSurfer_Destrieux' in name for name in available_connectomes.keys()):
            summary['available_atlases'].append('FreeSurfer_Destrieux')
        
        return summary

    def generate_report(self):
        """Generate the complete standardized report."""
        self.logger.info(f"Generating standardized report for {self.subject_name} ({self.species})")
        
        # Discover available connectomes
        available_connectomes = self.discover_connectomes()
        
        if not available_connectomes:
            self.report['warnings'].append("No connectome files found")
            self.logger.warning("No connectome files found")
            return self.report
        
        # Analyze each connectome
        for connectome_name, filepath in available_connectomes.items():
            self.logger.info(f"Analyzing connectome: {connectome_name}")
            
            matrix = self.load_connectome(filepath)
            if matrix is not None:
                basic_metrics = self.calculate_basic_metrics(matrix, connectome_name)
                graph_metrics = self.calculate_graph_metrics(matrix)
                
                self.report['connectomes'][connectome_name] = {
                    'filepath': filepath,
                    'basic_metrics': basic_metrics,
                    'graph_metrics': graph_metrics
                }
            else:
                self.report['warnings'].append(f"Failed to load connectome: {connectome_name}")
        
        # Quality control metrics
        self.report['quality_metrics'] = self.check_processing_quality()
        
        # Processing summary
        self.report['processing_summary'] = self.generate_processing_summary(available_connectomes)
        
        return self.report

    def save_report(self, output_filename='standardized_connectome_report.json'):
        """Save the report to a JSON file."""
        output_path = os.path.join(self.output_dir, output_filename)
        
        with open(output_path, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        self.logger.info(f"Report saved to: {output_path}")
        return output_path

    def print_summary(self):
        """Print a human-readable summary of the report."""
        print(f"\n{'='*60}")
        print(f"CONNECTOME PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Subject: {self.subject_name}")
        print(f"Species: {self.species.capitalize()}")
        print(f"FreeSurfer Version: {self.freesurfer_version}")
        print(f"Processing Date: {self.report['processing_date']}")
        
        print(f"\nCONNECTOMES GENERATED:")
        for connectome_name, data in self.report['connectomes'].items():
            metrics = data['basic_metrics']
            print(f"  {connectome_name}:")
            print(f"    Nodes: {metrics['n_nodes']}")
            print(f"    Total Streamlines: {metrics['total_streamlines']:,}")
            print(f"    Total Connections: {metrics['total_connections']:,}")
            print(f"    Connection Density: {metrics['connection_density']:.6f}")
        
        if self.report['warnings']:
            print(f"\nWARNINGS:")
            for warning in self.report['warnings']:
                print(f"  - {warning}")
        
        print(f"\nAtlases Available: {', '.join(self.report['processing_summary']['available_atlases'])}")
        print(f"{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(description='Generate standardized connectome report')
    parser.add_argument('--subject', required=True, help='Subject identifier')
    parser.add_argument('--output_dir', required=True, help='Output directory containing connectome files')
    parser.add_argument('--species', choices=['human', 'nhp'], default='human', help='Species type')
    parser.add_argument('--freesurfer_version', default='none', help='FreeSurfer version used')
    parser.add_argument('--output_filename', default='standardized_connectome_report.json', help='Output filename')
    
    args = parser.parse_args()
    
    # Create reporter instance
    reporter = ConnectomeReporter(
        subject_name=args.subject,
        output_dir=args.output_dir,
        species=args.species,
        freesurfer_version=args.freesurfer_version
    )
    
    # Generate report
    report = reporter.generate_report()
    
    # Save report
    output_path = reporter.save_report(args.output_filename)
    
    # Print summary
    reporter.print_summary()
    
    return output_path

if __name__ == "__main__":
    main()