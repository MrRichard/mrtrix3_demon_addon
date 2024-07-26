import os
import csv
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import pyplot as plt
from matplotlib.offsetbox import TextArea, DrawingArea, OffsetImage, AnnotationBbox

class NetworkAnalysis:
    def __init__(self, csv_file):
        self.csv_file = csv_file
        self.matrix = self.load_csv()
        self.adjacency_matrix = None
        self.adjacency_graph = None
        self.threshold = 0
        
    def load_csv(self):
        with open(self.csv_file, 'r') as f:
            reader = csv.reader(f)
            matrix = list(reader)
        return np.array(matrix, dtype=float)
        
    def plot_corr_network(self, labels_file, output_file='correlation_matrix.png'):
        with open(labels_file, 'r') as f:
            labels = f.read().splitlines()
            
        if len(labels) != len(self.matrix):
            raise ValueError("Number of labels does not match the size of the correlation matrix.")
        
        # Create a DataFrame from the correlation matrix
        df = pd.DataFrame(self.matrix, index=labels, columns=labels)
        
        # Plot the correlation matrix
        plt.figure(figsize=(40, 40))
        plt.matshow(df.corr(), fignum=1)
        plt.xticks(range(len(df.columns)), df.columns, rotation=45)
        plt.yticks(range(len(df.columns)), df.columns)
        plt.colorbar()
        plt.title('Correlation Matrix', fontsize=10)
        plt.savefig(output_file)  # Save the plot to a PNG file
        plt.close()  # Close the plot to free up memory
        
    def create_adjacency_matrix(self, threshold):
        """Create a binary adjacency matrix from the connectivity matrix based on a threshold."""
        
        self.threshold=threshold
        self.adjacency_matrix = np.where(self.matrix>threshold, 1, 0)
        
        # Create a DataFrame for the adjacency matrix
        df_adj = pd.DataFrame(self.adjacency_matrix)
        
        # Plot the adjacency matrix
        plt.figure(figsize=(10, 10))
        plt.matshow(df_adj, cmap='gray', fignum=1)  # Use grayscale colormap
        plt.title('Adjacency Matrix', fontsize=10)
        plt.colorbar()
        plt.savefig('adjacency_matrix.png', bbox_inches='tight')  # Save the plot to a PNG file
        plt.close()  # Close the plot to free up memory
        
        return True
    
    def calculate_graph_metrics(self):
        """Calculate and return various metrics for the graph."""
        if self.adjacency_matrix is None:
            raise ValueError("Adjacency matrix not created. Please create it first.")
        
        G = nx.Graph(self.adjacency_matrix)  # Create a graph from the adjacency matrix
        
        # Calculate metrics
        connectivity = nx.node_connectivity(G)  # Node connectivity
        assortativity = nx.degree_assortativity_coefficient(G)  # Assortativity coefficient
        degree_centrality = nx.degree_centrality(G)  # Degree centrality
        closeness_centrality = nx.closeness_centrality(G)  # Closeness centrality
        betweenness_centrality = nx.betweenness_centrality(G)  # Betweenness centrality
        eigenvector_centrality = nx.eigenvector_centrality(G)  # Eigenvector centrality
        diameter = nx.diameter(G) if nx.is_connected(G) else float('inf')  # Diameter
        average_clustering = nx.average_clustering(G)  # Average clustering coefficient
        
        return {
            'connectivity': connectivity,
            'assortativity': assortativity,
            'degree_centrality': degree_centrality,
            'closeness_centrality': closeness_centrality,
            'betweenness_centrality': betweenness_centrality,
            'eigenvector_centrality': eigenvector_centrality,
            'diameter': diameter,
            'average_clustering': average_clustering
        }