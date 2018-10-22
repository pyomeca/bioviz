import matplotlib.pyplot as plt
import seaborn as sns


def get_style(style='mrtnz', figsize='one_half_column'):
    style_dict = {}

    golden_ratio = 1.618

    if figsize == 'minimal':
        width = 1.1811023622
    elif figsize == 'one_col':
        width = 3.5433070866
    elif figsize == 'one_half_col':
        width = 5.5118110236
    elif figsize == 'two_col':
        width = 7.4803149606
    else:
        width = figsize
        print(f'custom figsize: {width}, {width / golden_ratio}')
    style_dict.update({'figure.figsize': (width, width / golden_ratio)})

    if style == 'mrtnz' or style == 'mrtnz_tex':
        style_dict.update({
            'axes.titlesize': 16,
            'axes.labelsize': 16,
            'xtick.labelsize': 12,
            'ytick.labelsize': 12,
            'legend.fontsize': 12,
            'pdf.fonttype': 42,
            'ps.fonttype': 42
        })
        if style == 'mrtnz_tex':
            style_dict.update({
                'text.usetex': True,
                'font.family': 'serif',
            })
    else:
        raise NotImplementedError(f'Style {style} is not available')
    return style_dict


def show(save=False, despine=True):
    if despine:
        sns.despine(offset=10, trim=True)
    else:
        sns.despine(offset=0, trim=False)
    plt.tight_layout()
    if save:
        plt.savefig(save, transparent=True, dpi=300)
    plt.show()
