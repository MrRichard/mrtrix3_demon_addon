#!/usr/bin/env python3
"""
Universal Standardized Reporting System for Human and NHP Connectomes
Generates consistent reports regardless of species or available atlases.
Enhanced with comprehensive graph theory metrics.
"""

import argparse
import json
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import glob

class PureNumpyGraphMetrics:
    """
    Graph theory metrics implementation using only NumPy and SciPy.
    No external dependencies to avoid version conflicts.
    """
    
    def calculate_comprehensive_metrics(self, matrix):
        """Calculate all graph metrics without external dependencies."""
        if matrix is None:
            return {}
        
        # Ensure symmetric matrix
        matrix = np.maximum(matrix, matrix.T)
        
        metrics = {}
        
        # Basic connectivity metrics
        metrics.update(self._basic_connectivity_metrics(matrix))
        
        # Weighted node metrics
        metrics.update(self._weighted_node_metrics(matrix))
        
        # Clustering metrics
        metrics.update(self._clustering_metrics(matrix))
        
        # Path length and efficiency metrics
        metrics.update(self._path_efficiency_metrics(matrix))
        
        # Small-world metrics
        metrics.update(self._small_world_metrics(matrix))
        
        # Network topology metrics
        metrics.update(self._topology_metrics(matrix))
        
        return metrics
    
    def _basic_connectivity_metrics(self, matrix):
        """Basic connectivity statistics."""
        n_nodes = matrix.shape[0]
        
        # Binary version for some calculations
        binary_matrix = (matrix > 0).astype(int)
        
        # Connection counts
        total_connections = int(np.sum(binary_matrix) / 2)  # Symmetric matrix
        possible_connections = n_nodes * (n_nodes - 1) / 2
        connection_density = total_connections / possible_connections
        
        # Weighted connections
        total_weight = float(np.sum(matrix) / 2)
        nonzero_weights = matrix[matrix > 0]
        
        return {
            'n_nodes': n_nodes,
            'total_connections': total_connections,
            'connection_density': round(connection_density, 6),
            'total_weight': round(total_weight, 3),
            'mean_edge_weight': round(float(np.mean(nonzero_weights)), 3) if len(nonzero_weights) > 0 else 0.0,
            'std_edge_weight': round(float(np.std(nonzero_weights)), 3) if len(nonzero_weights) > 0 else 0.0,
            'sparsity': round(1 - connection_density, 6)
        }
    
    def _weighted_node_metrics(self, matrix):
        """Node-level metrics for weighted networks."""
        # Node strength (weighted degree)
        node_strength = np.sum(matrix, axis=1)
        
        # Binary degree
        binary_matrix = (matrix > 0).astype(int)
        node_degree = np.sum(binary_matrix, axis=1)
        
        return {
            'mean_node_strength': round(float(np.mean(node_strength)), 3),
            'std_node_strength': round(float(np.std(node_strength)), 3),
            'max_node_strength': round(float(np.max(node_strength)), 3),
            'mean_degree': round(float(np.mean(node_degree)), 3),
            'std_degree': round(float(np.std(node_degree)), 3),
            'max_degree': int(np.max(node_degree)),
            'strength_degree_correlation': round(float(np.corrcoef(node_strength, node_degree)[0, 1]), 6) if len(node_strength) > 1 else 0.0
        }
    
    def _clustering_metrics(self, matrix):
        """Calculate clustering coefficients."""
        # Binary clustering coefficient
        binary_clustering = self._binary_clustering_coefficient(matrix)
        
        # Weighted clustering coefficient
        weighted_clustering = self._weighted_clustering_coefficient(matrix)
        
        return {
            'binary_clustering_coefficient': round(binary_clustering, 6),
            'weighted_clustering_coefficient': round(weighted_clustering, 6),
            'mean_clustering_coefficient': round(binary_clustering, 6)  # For backward compatibility
        }
    
    def _binary_clustering_coefficient(self, matrix):
        """Calculate binary clustering coefficient."""
        binary_matrix = (matrix > 0).astype(int)
        n_nodes = binary_matrix.shape[0]
        clustering_coeffs = []
        
        for i in range(n_nodes):
            neighbors = np.where(binary_matrix[i] > 0)[0]
            k = len(neighbors)
            
            if k < 2:
                clustering_coeffs.append(0.0)
            else:
                # Count triangles
                possible_edges = k * (k - 1) / 2
                actual_edges = np.sum(binary_matrix[np.ix_(neighbors, neighbors)]) / 2
                clustering_coeffs.append(actual_edges / possible_edges)
        
        return float(np.mean(clustering_coeffs))
    
    def _weighted_clustering_coefficient(self, matrix):
        """Calculate weighted clustering coefficient (Onnela et al., 2005)."""
        n_nodes = matrix.shape[0]
        clustering_coeffs = []
        
        # Normalize weights to [0,1] for geometric mean calculation
        max_weight = np.max(matrix)
        if max_weight > 0:
            norm_matrix = matrix / max_weight
        else:
            norm_matrix = matrix
        
        for i in range(n_nodes):
            neighbors = np.where(matrix[i] > 0)[0]
            k = len(neighbors)
            
            if k < 2:
                clustering_coeffs.append(0.0)
            else:
                numerator = 0.0
                denominator = 0.0
                
                for j in neighbors:
                    for h in neighbors:
                        if j != h:
                            w_ij = norm_matrix[i, j]
                            w_ih = norm_matrix[i, h]
                            w_jh = norm_matrix[j, h]
                            
                            # Geometric mean of triangle weights
                            numerator += (w_ij * w_ih * w_jh) ** (1/3)
                            denominator += w_ij * w_ih
                
                if denominator > 0:
                    clustering_coeffs.append(numerator / denominator)
                else:
                    clustering_coeffs.append(0.0)
        
        return float(np.mean(clustering_coeffs))
    
    def _path_efficiency_metrics(self, matrix):
        """Calculate path length and efficiency metrics."""
        # Use binary matrix for path calculations
        binary_matrix = (matrix > 0).astype(int)
        
        # Calculate shortest paths using Floyd-Warshall
        path_matrix = self._floyd_warshall(binary_matrix)
        
        # Extract finite path lengths
        finite_paths = path_matrix[np.isfinite(path_matrix) & (path_matrix > 0)]
        
        if len(finite_paths) > 0:
            characteristic_path_length = float(np.mean(finite_paths))
            global_efficiency = float(np.mean(1.0 / finite_paths))
        else:
            characteristic_path_length = np.inf
            global_efficiency = 0.0
        
        # Local efficiency
        local_efficiency = self._local_efficiency(binary_matrix)
        
        # Global efficiency approximation (for backward compatibility)
        degrees = np.sum(binary_matrix, axis=1)
        global_efficiency_approx = float(np.mean(degrees) / (len(binary_matrix) - 1))
        
        return {
            'characteristic_path_length': round(characteristic_path_length, 6) if characteristic_path_length != np.inf else None,
            'global_efficiency': round(global_efficiency, 6),
            'local_efficiency': round(local_efficiency, 6),
            'global_efficiency_approx': round(global_efficiency_approx, 6)  # For backward compatibility
        }
    
    def _floyd_warshall(self, binary_matrix):
        """Floyd-Warshall algorithm for all-pairs shortest paths."""
        n = binary_matrix.shape[0]
        dist = np.full((n, n), np.inf)
        
        # Initialize distances
        np.fill_diagonal(dist, 0)
        for i in range(n):
            for j in range(n):
                if binary_matrix[i, j] > 0:
                    dist[i, j] = 1
        
        # Floyd-Warshall
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    if dist[i, k] + dist[k, j] < dist[i, j]:
                        dist[i, j] = dist[i, k] + dist[k, j]
        
        return dist
    
    def _local_efficiency(self, binary_matrix):
        """Calculate local efficiency."""
        n_nodes = binary_matrix.shape[0]
        local_efficiencies = []
        
        for i in range(n_nodes):
            neighbors = np.where(binary_matrix[i] > 0)[0]
            k = len(neighbors)
            
            if k < 2:
                local_efficiencies.append(0.0)
            else:
                # Create subgraph of neighbors
                subgraph = binary_matrix[np.ix_(neighbors, neighbors)]
                
                # Calculate efficiency within subgraph
                subgraph_paths = self._floyd_warshall(subgraph)
                finite_subpaths = subgraph_paths[np.isfinite(subgraph_paths) & (subgraph_paths > 0)]
                
                if len(finite_subpaths) > 0:
                    local_efficiencies.append(np.mean(1.0 / finite_subpaths))
                else:
                    local_efficiencies.append(0.0)
        
        return float(np.mean(local_efficiencies))
    
    def _small_world_metrics(self, matrix, n_random=5):
        """Calculate small-world metrics."""
        binary_matrix = (matrix > 0).astype(int)
        
        # Real network metrics
        real_clustering = self._binary_clustering_coefficient(matrix)
        path_matrix = self._floyd_warshall(binary_matrix)
        finite_paths = path_matrix[np.isfinite(path_matrix) & (path_matrix > 0)]
        
        if len(finite_paths) > 0:
            real_path_length = float(np.mean(finite_paths))
        else:
            return {
                'small_worldness': 0.0,
                'normalized_clustering': 0.0,
                'normalized_path_length': 0.0
            }
        
        # Generate random networks
        n_nodes = matrix.shape[0]
        n_edges = int(np.sum(binary_matrix) / 2)
        
        random_clusterings = []
        random_path_lengths = []
        
        for _ in range(n_random):
            random_matrix = self._generate_random_network(n_nodes, n_edges)
            
            rand_clustering = self._binary_clustering_coefficient(random_matrix)
            rand_paths = self._floyd_warshall(random_matrix)
            rand_finite_paths = rand_paths[np.isfinite(rand_paths) & (rand_paths > 0)]
            
            if len(rand_finite_paths) > 0:
                random_clusterings.append(rand_clustering)
                random_path_lengths.append(np.mean(rand_finite_paths))
        
        if len(random_clusterings) == 0:
            return {
                'small_worldness': 0.0,
                'normalized_clustering': 0.0,
                'normalized_path_length': 0.0
            }
        
        mean_rand_clustering = np.mean(random_clusterings)
        mean_rand_path_length = np.mean(random_path_lengths)
        
        # Calculate small-world metrics
        gamma = real_clustering / mean_rand_clustering if mean_rand_clustering > 0 else 0
        lambda_val = real_path_length / mean_rand_path_length if mean_rand_path_length > 0 else 0
        sigma = gamma / lambda_val if lambda_val > 0 else 0
        
        return {
            'small_worldness': round(float(sigma), 6),
            'normalized_clustering': round(float(gamma), 6),
            'normalized_path_length': round(float(lambda_val), 6)
        }
    
    def _topology_metrics(self, matrix):
        """Additional topology metrics."""
        binary_matrix = (matrix > 0).astype(int)
        
        # Assortativity
        assortativity = self._assortativity(binary_matrix)
        
        return {
            'assortativity': round(float(assortativity), 6)
        }
    
    def _assortativity(self, binary_matrix):
        """Calculate degree assortativity coefficient."""
        degrees = np.sum(binary_matrix, axis=1)
        
        # Get all edges
        edges = []
        for i in range(binary_matrix.shape[0]):
            for j in range(i + 1, binary_matrix.shape[1]):
                if binary_matrix[i, j] > 0:
                    edges.append((degrees[i], degrees[j]))
        
        if len(edges) == 0:
            return 0.0
        
        edges = np.array(edges)
        
        # Calculate Pearson correlation coefficient
        if len(edges) > 1:
            correlation = np.corrcoef(edges[:, 0], edges[:, 1])[0, 1]
            return correlation if not np.isnan(correlation) else 0.0
        else:
            return 0.0
    
    def _generate_random_network(self, n_nodes, n_edges):
        """Generate random network with same nodes and edges."""
        matrix = np.zeros((n_nodes, n_nodes))
        edges_added = 0
        max_attempts = n_edges * 10  # Prevent infinite loops
        attempts = 0
        
        while edges_added < n_edges and attempts < max_attempts:
            i, j = np.random.randint(0, n_nodes, 2)
            attempts += 1
            
            if i != j and matrix[i, j] == 0:
                matrix[i, j] = 1
                matrix[j, i] = 1
                edges_added += 1
        
        return matrix


class ConnectomeReporter:
    def __init__(self, subject_name, output_dir, species='human', freesurfer_version='none'):
        self.subject_name = subject_name
        self.output_dir = output_dir
        self.species = species
        self.freesurfer_version = freesurfer_version
        self.graph_calculator = PureNumpyGraphMetrics()
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
        """Discover all available connectome files in the output directory and common subdirectories."""
        connectome_patterns = {
            'Brainnetome_counts': 'connectome_Brainnetome_counts.csv',
            'Brainnetome_scaled': 'connectome_Brainnetome_scaled.csv',
            'FreeSurfer_DK_counts': 'connectome_FreeSurfer_DK_counts.csv',
            'FreeSurfer_DK_scaled': 'connectome_FreeSurfer_DK_scaled.csv',
            'FreeSurfer_Destrieux_counts': 'connectome_FreeSurfer_Destrieux_counts.csv',
            'FreeSurfer_Destrieux_scaled': 'connectome_FreeSurfer_Destrieux_scaled.csv'
        }
        
        # Common subdirectories where connectomes might be located
        search_directories = [
            self.output_dir,
            os.path.join(self.output_dir, 'DTI', 'mrtrix3_outputs'),
            os.path.join(self.output_dir, 'mrtrix3_outputs'),
            os.path.join(self.output_dir, 'connectomes'),
            os.path.join(self.output_dir, 'results')
        ]
        
        available_connectomes = {}
        
        for search_dir in search_directories:
            if not os.path.exists(search_dir):
                self.logger.debug(f"Search directory does not exist: {search_dir}")
                continue
                
            self.logger.info(f"Searching for connectomes in: {search_dir}")
            
            for name, filename in connectome_patterns.items():
                if name in available_connectomes:  # Already found this connectome
                    continue
                    
                filepath = os.path.join(search_dir, filename)
                if os.path.exists(filepath):
                    available_connectomes[name] = filepath
                    self.logger.info(f"Found connectome: {name} in {search_dir}")
            
            # Also search for any CSV files that might be connectomes
            try:
                csv_files = glob.glob(os.path.join(search_dir, "*.csv"))
                for csv_file in csv_files:
                    filename = os.path.basename(csv_file)
                    if 'connectome' in filename.lower() or 'matrix' in filename.lower():
                        # Try to determine the type from filename
                        connectome_key = filename.replace('.csv', '')
                        if connectome_key not in available_connectomes.values():
                            self.logger.info(f"Found potential connectome file: {csv_file}")
                            # Only add if we haven't found a standard named version
                            if not any(connectome_key.replace('_', '').lower() in existing_name.lower().replace('_', '') 
                                    for existing_name in available_connectomes.keys()):
                                available_connectomes[connectome_key] = csv_file
            except Exception as e:
                self.logger.debug(f"Error scanning for CSV files in {search_dir}: {e}")
        
        if not available_connectomes:
            self.logger.warning("No connectome files found in any search directories")
            # List what files are actually in the directories for debugging
            for search_dir in search_directories:
                if os.path.exists(search_dir):
                    try:
                        files = os.listdir(search_dir)
                        self.logger.info(f"Files in {search_dir}: {files[:10]}...")  # Show first 10 files
                    except Exception as e:
                        self.logger.debug(f"Cannot list files in {search_dir}: {e}")
        
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
        """Calculate comprehensive graph theory metrics using enhanced implementation."""
        if matrix is None:
            return {}
        
        # Use the enhanced graph calculator
        enhanced_metrics = self.graph_calculator.calculate_comprehensive_metrics(matrix)
        
        return enhanced_metrics

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
                
                # Add FreeSurfer version info for FreeSurfer-derived connectomes
                connectome_info = {
                    'filepath': filepath,
                    'basic_metrics': basic_metrics,
                    'graph_metrics': graph_metrics
                }
                
                # Add FreeSurfer version for FreeSurfer-derived atlases
                if 'FreeSurfer' in connectome_name:
                    connectome_info['freesurfer_version'] = self.freesurfer_version
                    connectome_info['atlas_source'] = 'FreeSurfer-derived'
                else:
                    connectome_info['atlas_source'] = 'Template-based'
                
                self.report['connectomes'][connectome_name] = connectome_info
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
            graph_metrics = data['graph_metrics']
            atlas_source = data.get('atlas_source', 'Unknown')
            
            print(f"  {connectome_name}:")
            print(f"    Atlas Source: {atlas_source}")
            if 'freesurfer_version' in data:
                print(f"    FreeSurfer Version: {data['freesurfer_version']}")
            print(f"    Nodes: {metrics['n_nodes']}")
            print(f"    Total Streamlines: {metrics['total_streamlines']:,}")
            print(f"    Total Connections: {metrics['total_connections']:,}")
            print(f"    Connection Density: {metrics['connection_density']:.6f}")
            print(f"    Small-worldness: {graph_metrics.get('small_worldness', 'N/A')}")
            print(f"    Clustering Coefficient: {graph_metrics.get('binary_clustering_coefficient', 'N/A')}")
        
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