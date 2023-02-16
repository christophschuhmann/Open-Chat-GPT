import math
from typing import List

import numpy as np
import scipy.sparse as sp
import torch
from scipy.sparse import csr_matrix
from sentence_transformers import SentenceTransformer
from torch import Tensor
from tqdm import tqdm

THRESHOLD = 0.65


def embed_data(data, key="query", model_name="all-MiniLM-L6-v2", cores=1, gpu=False, batch_size=128):
    """
    Embed the sentences/text using the MiniLM language model (which uses mean pooling)
    """
    print("Embedding data")
    model = SentenceTransformer(model_name)
    print("Model loaded")

    sentences = data[key].tolist()
    unique_sentences = data[key].unique()
    print("Unique sentences", len(unique_sentences))

    if cores == 1:
        embeddings = model.encode(unique_sentences, show_progress_bar=True, batch_size=batch_size)
    else:
        devices = ["cpu"] * cores
        if gpu:
            devices = None  # use all CUDA devices

        # Start the multi-process pool on multiple devices
        print("Multi-process pool starting")
        pool = model.start_multi_process_pool(devices)
        print("Multi-process pool started")

        chunk_size = math.ceil(len(unique_sentences) / cores)

        # Compute the embeddings using the multi-process pool
        embeddings = model.encode_multi_process(unique_sentences, pool, batch_size=batch_size, chunk_size=chunk_size)
        model.stop_multi_process_pool(pool)

    print("Embeddings computed")

    mapping = {sentence: embedding for sentence, embedding in zip(unique_sentences, embeddings)}
    embeddings = np.array([mapping[sentence] for sentence in sentences])

    return embeddings


def cos_sim(a: Tensor, b: Tensor):
    """
    Computes the cosine similarity cos_sim(a[i], b[j]) for all i and j.
    :return: Matrix with res[i][j]  = cos_sim(a[i], b[j])
    """
    if not isinstance(a, torch.Tensor):
        a = torch.tensor(np.array(a))

    if not isinstance(b, torch.Tensor):
        b = torch.tensor(np.array(b))

    if len(a.shape) == 1:
        a = a.unsqueeze(0)

    if len(b.shape) == 1:
        b = b.unsqueeze(0)

    a_norm = torch.nn.functional.normalize(a, p=2, dim=1)
    b_norm = torch.nn.functional.normalize(b, p=2, dim=1)
    return torch.mm(a_norm, b_norm.transpose(0, 1))


def compute_cos_sim_kernel(embs):
    A = cos_sim(embs, embs)
    adj_matrix = torch.zeros_like(A)
    adj_matrix[A > THRESHOLD] = 1
    adj_matrix[A <= THRESHOLD] = 0
    adj_matrix = adj_matrix.numpy().astype(np.float32)
    return adj_matrix


def k_hop_message_passing(A, node_features, k):
    """
    Compute the k-hop adjacency matrix and aggregated features using message passing.

    Parameters:
    A (numpy array): The adjacency matrix of the graph.
    node_features (numpy array): The feature matrix of the nodes.
    k (int): The number of hops for message passing.

    Returns:
    A_k (numpy array): The k-hop adjacency matrix.
    agg_features (numpy array): The aggregated feature matrix for each node in the k-hop neighborhood.
    """

    print("Compute the k-hop adjacency matrix")
    A_k = np.linalg.matrix_power(A, k)

    print("Aggregate the messages from the k-hop neighborhood:")
    agg_features = node_features.copy()

    for i in tqdm(range(k)):
        agg_features += np.matmul(np.linalg.matrix_power(A, i + 1), node_features)

    return A_k, agg_features


def k_hop_message_passing_sparse(A, node_features, k):
    """
    Compute the k-hop adjacency matrix and aggregated features using message passing.

    Parameters:
    A (numpy array or scipy sparse matrix): The adjacency matrix of the graph.
    node_features (numpy array or scipy sparse matrix): The feature matrix of the nodes.
    k (int): The number of hops for message passing.

    Returns:
    A_k (numpy array): The k-hop adjacency matrix.
    agg_features (numpy array): The aggregated feature matrix for each node in the k-hop neighborhood.
    """

    # Convert input matrices to sparse matrices if they are not already
    if not sp.issparse(A):
        A = sp.csr_matrix(A)
    if not sp.issparse(node_features):
        node_features = sp.csr_matrix(node_features)

    # Compute the k-hop adjacency matrix and the aggregated features
    A_k = A.copy()
    agg_features = node_features.copy()

    for i in tqdm(range(k)):
        # Compute the message passing for the k-hop neighborhood
        message = A_k.dot(node_features)
        # Apply a GCN layer to aggregate the messages
        agg_features = A_k.dot(agg_features) + message
        # Update the k-hop adjacency matrix by adding new edges
        A_k += A_k.dot(A)

    return A_k.toarray(), agg_features.toarray()
