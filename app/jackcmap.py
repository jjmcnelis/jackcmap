#!/usr/bin/env python3
import os
import sys
import pandas as pd
import numpy as np
from osgeo import gdal
from matplotlib import cm, colors

import bokeh.palettes as palettes
from bokeh.plotting import figure
from bokeh.server.server import Server
from bokeh.themes import built_in_themes
from bokeh.layouts import column, layout#, widgetbox
from bokeh.models.layouts import TabPanel, Tabs
from bokeh.io import output_notebook, show

from bokeh.models import (
    LinearColorMapper,
    LogColorMapper,
    ColumnDataSource,
    BasicTicker,
    LogTicker,
    ColorBar,
)

from bokeh.models.widgets import ( 
    Select,
    Slider,
    RangeSlider,
    DataTable,
    TableColumn,
    PreText,
)

f = "/app/test.tif"

# COLOR MAPS

default_grp = "Uniform Sequential"
default_plt = "plasma"
default_cmap = cm.get_cmap(default_plt)
default_nbins = default_cmap.N

cmaps = {
    'Uniform Sequential': [
        'viridis', 'plasma', 'inferno', 'magma', 'cividis',
    ],
    'Sequential': [
        'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds', 'YlOrBr',
        'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu', 'GnBu', 'PuBu', 'YlGnBu',
        'PuBuGn', 'BuGn', 'YlGn', 'binary', 'gist_yarg', 'gist_gray', 'gray',
        'bone', 'pink', 'spring', 'summer', 'autumn', 'winter', 'cool',
        'Wistia', 'hot', 'afmhot', 'gist_heat', 'copper',
    ],
    'Diverging': [
        'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu', 'RdYlBu', 'RdYlGn',
        'Spectral', 'coolwarm', 'bwr', 'seismic',
    ],
    'Cyclic': [
        'twilight', 'twilight_shifted', 'hsv',
    ],
    'Qualitative': [
        'Pastel1', 'Pastel2', 'Paired', 'Accent', 'Dark2', 'Set1', 'Set2',
        'Set3', 'tab10', 'tab20', 'tab20b', 'tab20c',
    ],
    'Miscellaneous': [
        'flag', 'prism', 'ocean', 'gist_earth', 'terrain', 'gist_stern', 
        'gnuplot', 'gnuplot2', 'CMRmap', 'cubehelix', 'brg', 'gist_rainbow',
        'rainbow', 'jet', 'nipy_spectral', 'gist_ncar',
    ],
}

map_methods = {
    "linear": LinearColorMapper, 
    "logarithmic": LogColorMapper,
}


def rgb2hex(red, green, blue):
    """Convert red, green, and blue to their hexadecimal equivalent."""
    return "#%02x%02x%02x" % (int(red), int(green), int(blue))


def hex2rgb(hexadec):
    """Convert hexadecimal to its red, green, and blue equivalent."""
    return tuple(int(hexadec.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))


################################################################################
#
# Mapfile
#
################################################################################

raster_class_template = """
CLASS
    NAME "{name}"
    EXPRESSION ([pixel] >= {min} AND [pixel] < {max})
    COLOR {red} {green} {blue}
END
"""

def get_raster_class(red, green, blue, lower_bound, upper_bound):
    """Returns a mapfile tail with just layers. Soon to be whole mapfile."""
    return raster_class_template.format(
        name="%s - %s" % (lower_bound, upper_bound),
        min=lower_bound,
        max=upper_bound,
        red=red,
        green=green,
        blue=blue,
    )

# print(get_raster_class(255, 255, 255, 0, 100))

# mclass = lambda d: """CLASS
#     NAME "{d[name]}"
#     EXPRESSION ([pixel] >= {d[min]} AND [pixel] < {d[max]})
#     COLOR {d[r]} {d[g]} {d[b]}
# END
# """.format(d=d)

# def mapfile(r, g, b, lower, upper):
#     """Returns a mapfile tail with just layers. Soon to be whole mapfile."""
#     return(mclass({
#         'name': lower+" - "+upper,
#         'min': lower,
#         'max': upper,
#         'r': r,
#         'g': g,
#         'b': b}))

""" --------------------------------------------------------------------------
COLOR MAP GENERATOR
matplotlib.org/api/_as_gen//matplotlib.colors.LinearSegmentedColormap.html
-------------------------------------------------------------------------- """


def get_colormap(min_, max_, palette, cnt, method="linear"):
    """ """

    # get the cm colormapper if the name was passed
    if type(palette) == str:
        cmap = cm.get_cmap(palette)

    # get arrays for which to sample the colormap
    colors_i = np.linspace(0, 1., cnt)
    colors_rgba = cmap(colors_i)
    indices = np.linspace(0, 1., cnt+1)

    # get bin breaks
    aindices = np.linspace(min_, max_, cnt + 1)
    blo, bhi = aindices[:-1], aindices[1:]

    # get dict of rgb breaks
    cdict = {}
    for ki, key in enumerate(('red', 'green', 'blue')):
        for i in range(cnt):
            cdict[key] = (indices[i], colors_rgba[i-1, ki], colors_rgba[i, ki])

    # Create mapped color ramp.
    mapper = colors.LinearSegmentedColormap(cmap.name+"_%d" % cnt, cdict, 1024)

    # Make a function to scale 8bit values.
    def scale8(c):
        return(int(c[0]*255), int(c[1]*255), int(c[2]*255), int(c[3]*255))

    # Get color scales as four-channel RGB, RGB, and hexadecimal.
    rgba = [scale8(c) for c in colors_rgba]
    rgb = [c[0:3] for c in rgba]
    hexa = [rgb2hex(r, g, b) for r, g, b, _ in rgba]

    # Determine best method to generate bokeh colormap.
    colormapper = map_methods[method]
    cmap = colormapper(
        palette=hexa,
        low=min_,
        high=max_,
    )

    # Make a color table and mapfile layers.
    rgbd, rgbm = dict(r=[], g=[], b=[], low=blo, high=bhi), []

    # Loop over enumerated rgba color groups.
    for i, col in enumerate(rgba):

        # Split out red, green, blue, alpha; append to corresponding list.
        r, g, b, a = col
        rgbd['r'].append(r)
        rgbd['g'].append(g)
        rgbd['b'].append(b)

        # Generate sequence of mapfile class strings; append to list.
        class_str = get_raster_class(r, g, b, blo[i], bhi[i])
        rgbm.append(class_str)

    # Make a data frame from the rgb dictionary.
    rgbt = pd.DataFrame(rgbd)

    # Return many of the color constructs. # "breaks": breaks,
    return({"df": rgbt,
            "map": rgbm,
            "hex": hexa,
            "rgba": rgba,
            "cmap": cmap,
            "cmap_mpl": mapper})


""" --------------------------------------------------------------------------
# RASTER
-------------------------------------------------------------------------- """


def read_raster(f, overview: int=3):
    """Returns the raster metadata required to use generate color ramp."""

    # Open raster dataset, get the band count, and get the first band.
    raster = gdal.Open(f)
    nbands = raster.RasterCount
    band = raster.GetRasterBand(1)

    # Get the nodata value and set matching cells to numpy.nan.
    array = band.ReadAsArray()
    nodata = band.GetNoDataValue()
    array[array == nodata] = np.nan

    # Get some statistics about the original array.
    bmin = np.nanmin(array)
    bmax = np.nanmax(array)
    mean = np.nanmean(array)
    std = np.nanstd(array)

    # Get size of x and y dim of the raster.
    shape = array.shape

    # size x or y > 2000 >>> replace array w nth overview array (base 1).
    if any([shape[0] > 2000, shape[1] > 2000]):
        band = band.GetOverview(overview)
        array = band.ReadAsArray()

    # Set nodata to numpy nan again (in case overview); add to dict.
    array[array == nodata] = np.nan
    array = np.flipud(array)

    # Dereference the open raster dataset.
    raster = None

    return(nbands, band, array, nodata, bmin, bmax, mean, std, shape)


""" --------------------------------------------------------------------------
 BUILD UI
-------------------------------------------------------------------------- """


def get_color_mapper(f):
    """ """

    # Get a giant tuple of raster details and unpack it.
    #nbands, band, array, nodata, bmin, bmax, mean, std, shape = read_raster(f)
    nbands, bnd1, arr1, nod1, min1, max1, avg1, std1, shp1 = read_raster(f)

    # Get the default color palette.
    mypalette = get_colormap(min1, max1, default_plt, default_nbins, "linear")

    # Reactive variable container.
    source = ColumnDataSource(data=mypalette['df'])

    # Draw the colorbar graphic separately from the plot.
    color_bar = ColorBar(
        color_mapper=mypalette['cmap'],
        ticker=BasicTicker(),
        label_standoff=8,
        border_line_color=None,
        location=(0, 0))

    # Initialize the plot.
    p = figure(
        x_range=(0, shp1[0]),
        y_range=(0, shp1[1]),
        width=600,
        height=450,
    )

    # Add raster to plot.
    img = p.image(
        image=[arr1],
        x=0,
        y=0,
        dw=shp1[0],
        dh=shp1[1],
    )
    # And update the layout with the color bar position right.
    p.add_layout(color_bar, "right")

    # # Slider for bin count adjustment.
    # ovrslider = Slider(
    #     start=0,
    #     end=1,
    #     value=1,
    #     step=1,
    #     title="nbins: ",
    # )

    # Dropdown to select the family of color ramps.
    group_select = Select(
        title="color group: ",
        value=default_grp,
        options=list(cmaps.keys()),
    )

    # Dropdown color ramp picker.
    color_select = Select(
        title="color: ",
        value=default_plt,
        options=cmaps[default_grp],
    )

    # Dropdown value map method (only linear and logarithmic for now).
    method_select = Select(
        title="map method: ",
        value="linear",
        options=["linear", "logarithmic"],
    )

    # Slider for value range constraint.
    range_slider = RangeSlider(
        start=min1,
        end=max1,
        value=(min1, max1),
        step=.1,
        title="norm range: ",
    )

    # Slider for bin count adjustment.
    nbin_slider = Slider(
        start=1,
        end=default_nbins,
        value=default_nbins,
        step=1,
        title="nbins: ",
    )

    # Make columns for table widget to display value range by color bin.
    columns = [
        TableColumn(field="r", title="r"),
        TableColumn(field="g", title="g"),
        TableColumn(field="b", title="b"),
        TableColumn(field="low", title="low"),
        TableColumn(field="high", title="high"),
    ]

    # Make the table.
    color_table = DataTable(
        source=source,
        columns=columns,
        width=275,
        height=400,
        fit_columns=True,
    )

    # Mapfile preview.
    class_txt = PreText(text="Placeholder", width=275, height=400)

    def update_palette_select(attr, old, new):
        pals = cmaps[group_select.value]
        color_select.options = pals
        color_select.value = pals[0]

    def update_plot(attr, old, new):

        # make sure bin slider doesn't exceed cmap.N
        cmap = cm.get_cmap(color_select.value)
        nbins = cmap.N
        if nbin_slider.value > nbins:
            nbin_slider.value = nbins
        nbin_slider.end = nbins

        rmin, rmax = range_slider.value

        # color table display
        mypalette = get_colormap(
            rmin,
            rmax,
            color_select.value,
            nbin_slider.value,
            method_select.value)
        source.data = dict(ColumnDataSource(data=mypalette['df']).data)

        img.glyph.color_mapper = mypalette['cmap']
        color_bar.update(color_mapper=mypalette['cmap'])

        class_txt.text = "".join(mypalette['map'][:4])


    group_select.on_change("value", update_palette_select)
    color_select.on_change("value", update_plot)
    method_select.on_change("value", update_plot)
    range_slider.on_change("value", update_plot)
    nbin_slider.on_change("value", update_plot)

    # initialize values
    update_plot(None, None, None)

    # build layout; push to browser
    tab1 = TabPanel(child=column(#widgetbox(
        group_select,
        color_select,
        method_select,
        range_slider,
        nbin_slider
    ), title="Options")
    tab2 = TabPanel(child=color_table, title="Colors")
    tab3 = TabPanel(child=class_txt, title="Mapfile")
    tabs = column(Tabs(tabs=[tab1, tab2, tab3], ))  # sizing_mode="fixed"

    return(layout([[tabs, p]], ))  # sizing_mode="fixed"


def modify_doc(doc, f=f):
    """Updates browser."""

    ui = get_color_mapper(f)

    # send to browser
    doc.add_root(ui)

""" --------------------------------------------------------------------------
SERVER bokeh/bokeh/blob/master/examples/howto/server_embed/standalone_embed.py
 Setting num_procs here means we can't touch the IOLoop before now, we must
 let Server handle that. If you need to explicitly handle IOLoops then you
 will need to use the lower level BaseServer class.
-------------------------------------------------------------------------- """

# check to see if the script is running in standalone mode
if __name__ == '__main__':

    # check for input file
    if len(sys.argv) == 2:
        if os.path.isfile(sys.argv[1]):
            f = sys.argv[1]
        else:
            print("Input is not a valid raster: "+str(sys.argv[1])+
                  "\nLoading test file.")

    # launch the server
    print('Opening Bokeh application on http://localhost:5006/')

    server = Server({'/': modify_doc}, num_procs=1)
    server.start()

    server.io_loop.add_callback(server.show, "/")
    server.io_loop.start()
