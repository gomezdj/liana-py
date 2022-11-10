import numpy as np

from plotnine import ggplot, geom_point, aes, \
    facet_grid, labs, theme_bw, theme, element_text, element_rect


def dotplot(adata, colour, size, source_labels=None,
            target_labels=None, top_n=None,
            orderby=None, inverse_colour=False,
            inverse_size=False, figure_size=(8, 6),
            return_fig=True) -> ggplot:
    """
    Dotplot interactions by source and target cells

    Parameters
    ----------
    adata
        `AnnData` object with `liana_res` in `adata.uns`
    colour

    size
    source_labels
    target_labels
    top_n
    orderby
    inverse_colour
    inverse_size
    figure_size
    return_fig

    Returns
    -------

    """
    assert 'liana_res' in adata.uns_keys()

    # extract results & create interaction col
    liana_mod = adata.uns['liana_res'].copy()
    liana_mod['interaction'] = liana_mod.ligand_complex + ' -> ' + liana_mod.receptor_complex

    # subset to only cell labels of interest
    if source_labels is not None:
        source_msk = np.isin(liana_mod.source, source_labels)
        liana_mod = liana_mod[source_msk]
    if target_labels is not None:
        target_msk = np.isin(liana_mod.target, target_labels)
        liana_mod = liana_mod[target_msk]

    # inverse sc if needed
    if inverse_colour:
        liana_mod[colour] = _inverse_scores(liana_mod[colour])
    if inverse_size:
        liana_mod[size] = _inverse_scores(liana_mod[size])

    if top_n is not None:
        # get the top_n for each interaction
        top_lrs = _aggregate_scores(liana_mod, what=orderby, how='max',
                                    entities=['interaction',
                                              'ligand_complex',
                                              'receptor_complex']
                                    )
        top_lrs = top_lrs.sort_values('score', ascending=False).head(top_n).interaction
        # Filter liana_res to the interactions in top_lrs
        liana_mod = liana_mod[liana_mod.interaction.isin(top_lrs)]

    # generate plot
    p = (ggplot(liana_mod, aes(x='target', y='interaction', colour=colour, size=size))
         + geom_point()
         + facet_grid('~source')
         + labs(color=str.capitalize(colour),
                size=str.capitalize(size),
                y="Interactions (Ligand -> Receptor)",
                x="")
         + theme_bw()
         + theme(legend_text=element_text(size=14),
                 strip_background=element_rect(fill="white"),
                 strip_text=element_text(size=20, colour="black"),
                 axis_text_y=element_text(size=10),
                 axis_text_x=element_text(size=12, face="bold"),
                 figure_size=figure_size
                 )
         )

    if return_fig:
        return p

    p.draw()


def _aggregate_scores(res, what, how, entities):
    return res.groupby(entities).agg(score=(what, how)).reset_index()

def _inverse_scores(score):
    return -np.log10(score + np.finfo(float).eps)