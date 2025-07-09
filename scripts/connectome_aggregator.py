#!/usr/bin/env python3
"""
Connectome Data Aggregator and Analyzer
Processes multiple standardized connectome reports and creates aggregated datasets and visualizations.
"""

import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class ConnectomeAggregator:
    def __init__(self, root_directory, output_directory="aggregated_analysis"):
        """
        Initialize the aggregator with root directory containing session folders.
        
        Args:
            root_directory (str): Path to directory containing session folders
            output_directory (str): Path for output files and plots
        """
        self.root_directory = Path(root_directory)
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(exist_ok=True)
        
        # Define atlas names and their variations
        self.atlases = {
            'Brainnetome': ['Brainnetome_counts', 'Brainnetome_scaled'],
            'FreeSurfer_DK': ['FreeSurfer_DK_counts', 'FreeSurfer_DK_scaled'],
            'FreeSurfer_Destrieux': ['FreeSurfer_Destrieux_counts', 'FreeSurfer_Destrieux_scaled']
        }
        
        # Initialize data storage
        self.all_data = {}
        self.aggregated_data = {}
        
        print(f"Connectome Aggregator initialized")
        print(f"Root directory: {self.root_directory}")
        print(f"Output directory: {self.output_directory}")

    def find_json_files(self):
        """Find all standardized_connectome_report.json files."""
        json_files = []
        
        # Search for JSON files in the expected structure
        for session_dir in self.root_directory.iterdir():
            if session_dir.is_dir():
                json_path = session_dir / "DTI" / "mrtrix3_outputs" / "standardized_connectome_report.json"
                if json_path.exists():
                    json_files.append(json_path)
                else:
                    # Also check for files directly in session directory
                    alt_json_path = session_dir / "standardized_connectome_report.json"
                    if alt_json_path.exists():
                        json_files.append(alt_json_path)
        
        print(f"Found {len(json_files)} JSON files")
        return json_files

    def load_all_data(self):
        """Load data from all JSON files."""
        json_files = self.find_json_files()
        
        if not json_files:
            raise FileNotFoundError("No JSON files found. Please check your directory structure.")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    subject_id = data.get('subject_id', json_file.parent.parent.parent.name)
                    self.all_data[subject_id] = data
                    
            except Exception as e:
                print(f"Error loading {json_file}: {e}")
        
        print(f"Successfully loaded {len(self.all_data)} datasets")

    def create_aggregated_dataframes(self):
        """Create aggregated DataFrames for each atlas."""
        
        for atlas_name, atlas_variations in self.atlases.items():
            print(f"\nProcessing {atlas_name} atlas...")
            
            # Initialize containers for this atlas
            basic_metrics_data = []
            graph_metrics_data = []
            
            for subject_id, data in self.all_data.items():
                connectomes = data.get('connectomes', {})
                
                # Process each variation (counts and scaled)
                for variation in atlas_variations:
                    if variation in connectomes:
                        connectome_data = connectomes[variation]
                        
                        # Extract basic metrics
                        basic_metrics = connectome_data.get('basic_metrics', {})
                        if basic_metrics:
                            basic_row = {
                                'subject_id': subject_id,
                                'atlas': atlas_name,
                                'metric_type': variation.split('_')[-1],  # 'counts' or 'scaled'
                                **basic_metrics
                            }
                            basic_metrics_data.append(basic_row)
                        
                        # Extract graph metrics
                        graph_metrics = connectome_data.get('graph_metrics', {})
                        if graph_metrics:
                            graph_row = {
                                'subject_id': subject_id,
                                'atlas': atlas_name,
                                'metric_type': variation.split('_')[-1],  # 'counts' or 'scaled'
                                **graph_metrics
                            }
                            graph_metrics_data.append(graph_row)
            
            # Create DataFrames
            if basic_metrics_data:
                basic_df = pd.DataFrame(basic_metrics_data)
                graph_df = pd.DataFrame(graph_metrics_data)
                
                # Store in aggregated data
                self.aggregated_data[atlas_name] = {
                    'basic_metrics': basic_df,
                    'graph_metrics': graph_df
                }
                
                print(f"  Basic metrics: {len(basic_df)} records")
                print(f"  Graph metrics: {len(graph_df)} records")

    def save_csv_files(self):
        """Save aggregated data to CSV files."""
        csv_dir = self.output_directory / "csv_files"
        csv_dir.mkdir(exist_ok=True)
        
        for atlas_name, dataframes in self.aggregated_data.items():
            # Save basic metrics
            basic_file = csv_dir / f"{atlas_name}_basic_metrics.csv"
            dataframes['basic_metrics'].to_csv(basic_file, index=False)
            
            # Save graph metrics
            graph_file = csv_dir / f"{atlas_name}_graph_metrics.csv"
            dataframes['graph_metrics'].to_csv(graph_file, index=False)
            
            print(f"Saved CSV files for {atlas_name}")
        
        print(f"\nCSV files saved to: {csv_dir}")

    def create_distribution_plots(self):
        """Create comprehensive distribution plots for scaled metrics."""
        
        # Set up plotting style
        plt.style.use('default')
        sns.set_palette("husl")
        
        # Create plots directory
        plots_dir = self.output_directory / "plots"
        plots_dir.mkdir(exist_ok=True)
        
        # Plot basic metrics
        self._plot_basic_metrics_distributions(plots_dir)
        
        # Plot graph metrics
        self._plot_graph_metrics_distributions(plots_dir)
        
        # Create comparison plots across atlases
        self._create_cross_atlas_comparisons(plots_dir)
        
        print(f"\nPlots saved to: {plots_dir}")

    def _plot_basic_metrics_distributions(self, plots_dir):
        """Plot distributions for basic metrics."""
        
        # Key basic metrics to visualize
        basic_metrics_of_interest = [
            'connection_density', 'mean_connection_strength', 
            'std_connection_strength', 'sparsity'
        ]
        
        for metric in basic_metrics_of_interest:
            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle(f'Basic Metric: {metric.replace("_", " ").title()} (Scaled Data)', fontsize=16, fontweight='bold')
            
            for i, (atlas_name, dataframes) in enumerate(self.aggregated_data.items()):
                # Get scaled data only
                scaled_data = dataframes['basic_metrics'][
                    dataframes['basic_metrics']['metric_type'] == 'scaled'
                ]
                
                if metric in scaled_data.columns and not scaled_data[metric].empty:
                    values = scaled_data[metric].dropna()
                    
                    # Distribution plot
                    axes[0, i].hist(values, bins=20, alpha=0.7, density=True, color=f'C{i}')
                    axes[0, i].axvline(values.mean(), color='red', linestyle='--', 
                                     label=f'Mean: {values.mean():.3f}')
                    axes[0, i].set_title(f'{atlas_name}\n(n={len(values)})')
                    axes[0, i].legend()
                    axes[0, i].grid(True, alpha=0.3)
                    
                    # Q-Q plot for normality assessment
                    stats.probplot(values, dist="norm", plot=axes[1, i])
                    axes[1, i].set_title(f'{atlas_name} - Q-Q Plot')
                    axes[1, i].grid(True, alpha=0.3)
                    
                    # Add normality test results
                    _, p_value = stats.shapiro(values) if len(values) <= 5000 else stats.jarque_bera(values)[:2]
                    axes[1, i].text(0.05, 0.95, f'Normality p-value: {p_value:.4f}', 
                                   transform=axes[1, i].transAxes, bbox=dict(boxstyle="round", facecolor='wheat'))
            
            plt.tight_layout()
            plt.savefig(plots_dir / f'basic_metrics_{metric}_distributions.png', dpi=300, bbox_inches='tight')
            plt.close()

    def _plot_graph_metrics_distributions(self, plots_dir):
        """Plot distributions for graph metrics."""
        
        # Key graph metrics to visualize
        graph_metrics_of_interest = [
            'binary_clustering_coefficient', 'global_efficiency', 
            'local_efficiency', 'small_worldness', 'assortativity'
        ]
        
        for metric in graph_metrics_of_interest:
            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle(f'Graph Metric: {metric.replace("_", " ").title()} (Scaled Data)', fontsize=16, fontweight='bold')
            
            for i, (atlas_name, dataframes) in enumerate(self.aggregated_data.items()):
                # Get scaled data only
                scaled_data = dataframes['graph_metrics'][
                    dataframes['graph_metrics']['metric_type'] == 'scaled'
                ]
                
                if metric in scaled_data.columns and not scaled_data[metric].empty:
                    values = scaled_data[metric].dropna()
                    
                    if len(values) > 0:
                        # Distribution plot
                        axes[0, i].hist(values, bins=20, alpha=0.7, density=True, color=f'C{i}')
                        axes[0, i].axvline(values.mean(), color='red', linestyle='--', 
                                         label=f'Mean: {values.mean():.3f}')
                        axes[0, i].set_title(f'{atlas_name}\n(n={len(values)})')
                        axes[0, i].legend()
                        axes[0, i].grid(True, alpha=0.3)
                        
                        # Q-Q plot for normality assessment
                        stats.probplot(values, dist="norm", plot=axes[1, i])
                        axes[1, i].set_title(f'{atlas_name} - Q-Q Plot')
                        axes[1, i].grid(True, alpha=0.3)
                        
                        # Add normality test results
                        if len(values) > 3:
                            _, p_value = stats.shapiro(values) if len(values) <= 5000 else stats.jarque_bera(values)[:2]
                            axes[1, i].text(0.05, 0.95, f'Normality p-value: {p_value:.4f}', 
                                           transform=axes[1, i].transAxes, bbox=dict(boxstyle="round", facecolor='wheat'))
            
            plt.tight_layout()
            plt.savefig(plots_dir / f'graph_metrics_{metric}_distributions.png', dpi=300, bbox_inches='tight')
            plt.close()

    def _create_cross_atlas_comparisons(self, plots_dir):
        """Create comparison plots across atlases."""
        
        # Violin plots comparing key metrics across atlases
        key_metrics = {
            'basic': ['connection_density', 'sparsity'],
            'graph': ['binary_clustering_coefficient', 'global_efficiency', 'small_worldness']
        }
        
        for metric_type, metrics in key_metrics.items():
            fig, axes = plt.subplots(1, len(metrics), figsize=(6*len(metrics), 8))
            if len(metrics) == 1:
                axes = [axes]
            
            fig.suptitle(f'Cross-Atlas Comparison: {metric_type.title()} Metrics (Scaled Data)', 
                        fontsize=16, fontweight='bold')
            
            for i, metric in enumerate(metrics):
                # Combine data from all atlases
                combined_data = []
                
                for atlas_name, dataframes in self.aggregated_data.items():
                    data_type = 'basic_metrics' if metric_type == 'basic' else 'graph_metrics'
                    scaled_data = dataframes[data_type][
                        dataframes[data_type]['metric_type'] == 'scaled'
                    ]
                    
                    if metric in scaled_data.columns:
                        values = scaled_data[metric].dropna()
                        for value in values:
                            combined_data.append({'Atlas': atlas_name, metric: value})
                
                if combined_data:
                    df_combined = pd.DataFrame(combined_data)
                    
                    # Create violin plot
                    sns.violinplot(data=df_combined, x='Atlas', y=metric, ax=axes[i])
                    axes[i].set_title(f'{metric.replace("_", " ").title()}')
                    axes[i].tick_params(axis='x', rotation=45)
                    axes[i].grid(True, alpha=0.3)
                    
                    # Add statistical annotations
                    atlas_names = df_combined['Atlas'].unique()
                    if len(atlas_names) > 1:
                        # Perform ANOVA
                        groups = [df_combined[df_combined['Atlas'] == atlas][metric].dropna() 
                                for atlas in atlas_names]
                        f_stat, p_value = stats.f_oneway(*groups)
                        axes[i].text(0.02, 0.98, f'ANOVA p-value: {p_value:.4f}', 
                                   transform=axes[i].transAxes, bbox=dict(boxstyle="round", facecolor='lightblue'),
                                   verticalalignment='top')
            
            plt.tight_layout()
            plt.savefig(plots_dir / f'cross_atlas_comparison_{metric_type}_metrics.png', 
                       dpi=300, bbox_inches='tight')
            plt.close()

    def generate_summary_statistics(self):
        """Generate summary statistics for each atlas and metric type."""
        
        summary_file = self.output_directory / "summary_statistics.txt"
        
        with open(summary_file, 'w') as f:
            f.write("CONNECTOME DATA SUMMARY STATISTICS\n")
            f.write("=" * 50 + "\n\n")
            
            for atlas_name, dataframes in self.aggregated_data.items():
                f.write(f"\n{atlas_name.upper()} ATLAS\n")
                f.write("-" * 30 + "\n")
                
                # Basic metrics summary
                f.write("\nBASIC METRICS (Scaled):\n")
                basic_scaled = dataframes['basic_metrics'][
                    dataframes['basic_metrics']['metric_type'] == 'scaled'
                ]
                
                numeric_cols = basic_scaled.select_dtypes(include=[np.number]).columns
                for col in numeric_cols:
                    if col not in ['subject_id']:
                        values = basic_scaled[col].dropna()
                        if len(values) > 0:
                            f.write(f"  {col}: Mean={values.mean():.4f}, "
                                   f"Std={values.std():.4f}, "
                                   f"Range=[{values.min():.4f}, {values.max():.4f}]\n")
                
                # Graph metrics summary
                f.write("\nGRAPH METRICS (Scaled):\n")
                graph_scaled = dataframes['graph_metrics'][
                    dataframes['graph_metrics']['metric_type'] == 'scaled'
                ]
                
                numeric_cols = graph_scaled.select_dtypes(include=[np.number]).columns
                for col in numeric_cols:
                    if col not in ['subject_id']:
                        values = graph_scaled[col].dropna()
                        if len(values) > 0:
                            f.write(f"  {col}: Mean={values.mean():.4f}, "
                                   f"Std={values.std():.4f}, "
                                   f"Range=[{values.min():.4f}, {values.max():.4f}]\n")
        
        print(f"Summary statistics saved to: {summary_file}")

    def run_complete_analysis(self):
        """Run the complete analysis pipeline."""
        print("Starting complete connectome analysis...")
        print("=" * 50)
        
        # Load all data
        self.load_all_data()
        
        # Create aggregated DataFrames
        self.create_aggregated_dataframes()
        
        # Save CSV files
        self.save_csv_files()
        
        # Create visualizations
        self.create_distribution_plots()
        
        # Generate summary statistics
        self.generate_summary_statistics()
        
        print("\n" + "=" * 50)
        print("Analysis complete!")
        print(f"Results saved to: {self.output_directory}")
        print("\nGenerated files:")
        print("- CSV files: csv_files/")
        print("- Plots: plots/")
        print("- Summary: summary_statistics.txt")


def main():
    """Main function to run the analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Aggregate and analyze connectome data')
    parser.add_argument('--root_dir', required=True, 
                       help='Root directory containing session folders with connectome reports')
    parser.add_argument('--output_dir', default='aggregated_analysis',
                       help='Output directory for results (default: aggregated_analysis)')
    
    args = parser.parse_args()
    
    # Create aggregator and run analysis
    aggregator = ConnectomeAggregator(args.root_dir, args.output_dir)
    aggregator.run_complete_analysis()


if __name__ == "__main__":
    main()