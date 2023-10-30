from anndata import AnnData
import numpy as np
from scipy.spatial import cKDTree
from sklearn.preprocessing import normalize
from liana._constants._docs import d

def _gaussian(distance_mtx, l):
    return np.exp(-(distance_mtx ** 2.0) / (2.0 * l ** 2.0))

def _misty_rbf(distance_mtx, l):
    return np.exp(-(distance_mtx ** 2.0) / (l ** 2.0))

def _exponential(distance_mtx, l):
    return np.exp(-distance_mtx / l)

def _linear(distance_mtx, l):
    connectivity = 1 - distance_mtx / l
    return np.clip(connectivity, a_min=0, a_max=np.inf)


def spatial_neighbors(adata: AnnData,
                      bandwidth=None,
                      cutoff=None,
                      max_dist_ratio=3,
                      kernel='gaussian',
                      set_diag=False,
                      zoi=0,
                      standardize=False,
                      spatial_key="spatial",
                      key_added='spatial',
                      reference=None,
                      inplace=True
                      ):
    """
    Generate spatial connectivity weights using Euclidean distance.
    
    Parameters
    ----------
    
    %(adata)s
    bandwidth
         Denotes signaling length (`l`). Corresponds to the units in which spatial coordinates are expressed.
    cutoff
        Values below this cutoff will be set to 0.
    max_dist_ratio
        Maximum distance ratio used when calculate pairwise Euclidean distances. Default is 3 (x the bandwidth).
    kernel
        Kernel function used to generate connectivity weights. The following options are available:
        ['gaussian', 'exponential', 'linear', 'misty_rbf']
    set_diag
        Logical, sets connectivity diagonal to 0 if `False`. Default is `True`.
    zoi
        Zone of indifference. Values below this cutoff will be set to `np.inf`.
    standardize
        Whether to (l1) standardize spatial proximities (connectivities) so that they sum to 1.
        This plays a role when weighing border regions prior to downstream methods, as the number of spots
        in the border region (and hence the sum of proximities) is smaller than the number of spots in the center.
        Relevant for methods with unstandardized scores (e.g. product). Default is `False`.
    %(spatial_key)s
    key_added
        Key to add to `adata.obsp` if `inplace = True`.
    %(inplace)s
        
    Notes
    -----
    This function is adapted from mistyR, and is set to be consistent with
    the `squidpy.gr.spatial_neighbors` function in the `squidpy` package. 
    It is intended to be a minimalist implementation of spatial connectivity weights,
    for non-generic use cases, it should be replaced by `squidpy.gr.spatial_neighbors`.
    
    Returns
    -------
    If ``inplace = False``, returns an `np.array` with spatial connectivity weights.
    Otherwise, modifies the ``adata`` object with the following key:
        - :attr:`anndata.AnnData.obsp` ``['{key_added}_connectivities']`` with the aforementioned array
        
    """

    if cutoff is None:
        raise ValueError("`cutoff` must be provided!")
    assert spatial_key in adata.obsm
    families = ['gaussian', 'exponential', 'linear', 'misty_rbf']
    if kernel not in families:
        raise AssertionError(f"{kernel} must be a member of {families}")
    if bandwidth is None:
        raise ValueError("Please specify a bandwidth")

    max_distance = bandwidth * max_dist_ratio
    coords = adata.obsm[spatial_key]
    tree = cKDTree(coords)
    
    if reference is not None:
        reference = cKDTree(reference)
        dist = reference.sparse_distance_matrix(tree,
                                                max_distance=max_distance,
                                                output_type="coo_matrix")
    else:
        dist = tree.sparse_distance_matrix(tree,
                                           max_distance=max_distance,
                                           output_type="coo_matrix")

    
    dist = dist.tocsr()

    # prevent float overflow
    bandwidth = np.array(bandwidth, dtype=np.float64)

    # define zone of indifference
    dist.data[dist.data < zoi] = np.inf

    # NOTE: dist gets converted to a connectivity matrix
    if kernel == 'gaussian':
        dist.data = _gaussian(dist.data, bandwidth)
    elif kernel == 'misty_rbf':
        dist.data = _misty_rbf(dist.data, bandwidth)
    elif kernel == 'exponential':
        dist.data = _exponential(dist.data, bandwidth)
    elif kernel == 'linear':
        dist.data = _linear(dist.data, bandwidth)
    else:
        raise ValueError("Please specify a valid family to generate connectivity weights")

    if not set_diag:
        dist.setdiag(0)
    if cutoff is not None:
        dist.data = dist.data * (dist.data > cutoff)
    if standardize:
        dist = normalize(dist, axis=1, norm='l1')

    spot_n = dist.shape[0]
    if reference is None:
        assert spot_n == adata.shape[0]
    if spot_n > 1000:
        dist = dist.astype(np.float32)

    if inplace:
        if reference is not None:
            adata.obsm[f'{key_added}_connectivities'] = dist.T
        else:
            adata.obsp[f'{key_added}_connectivities'] = dist

    return None if inplace else dist
