// ERA5-Land daily Tmax for Rajshahi — paste into https://code.earthengine.google.com
// Exports a CSV (date, tmax_c) to Google Drive. Use it with:
//   heatcast run --data path/to/rajshahi_tmax_daily.csv
// (the Python fetcher `heatcast fetch --source gee` does the same thing without Drive)

var point = ee.Geometry.Point([88.6042, 24.3745]);   // Rajshahi
var region = point;                                   // or point.buffer(10000) for a 10 km mean

var col = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
  .filterDate('1991-01-01', '2026-01-01')
  .select('temperature_2m_max');

var fc = col.map(function (img) {
  var v = img.reduceRegion({reducer: ee.Reducer.mean(), geometry: region, scale: 11132})
             .get('temperature_2m_max');
  return ee.Feature(null, {
    date: img.date().format('YYYY-MM-dd'),
    tmax_c: ee.Number(v).subtract(273.15)
  });
});

print('days:', fc.size());
print(ui.Chart.feature.byFeature(fc.limit(5000), 'date', 'tmax_c').setOptions({title: 'Rajshahi Tmax (°C)'}));

Export.table.toDrive({
  collection: fc,
  description: 'rajshahi_tmax_daily',
  fileFormat: 'CSV',
  selectors: ['date', 'tmax_c']
});
