import altair as alt
import pandas as pd
from vega_datasets import data

cars = pd.melt(data.cars(), ['Horsepower', 'Origin', 'Name', 'Year'])
cars.head()

select_box = alt.binding_select(options=list(cars['variable'].unique()))
selection = alt.selection_single(name='y_axis', fields=['variable'], bind=select_box)

alt.Chart(cars).mark_point().encode(
    x='Horsepower',
    y='value',
    color='Origin',
    tooltip='Name'
).add_selection(
    selection
).transform_filter(
    selection
).serve()
