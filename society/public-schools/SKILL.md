---
name: public-schools
description: Retrieve public school locations in the USA. Query by name, city, state, grade level, or enrollment. Returns point geometries with school details and contact information.
---

# Public Schools Skill

## Description

This skill retrieves locations and attributes of public schools in the United States by accessing the ArcGIS Feature Service at the following URL:

```
https://services5.arcgis.com/HDRa0B57OVrv2E1q/ArcGIS/rest/services/Public_Schools/FeatureServer/0
```

**Service Details:**
- Maximum record count: 2000
- Spatial reference: WGS84 (EPSG:4326) - no transformation needed

The service returns the following columns:

- **OBJECTID_1**: System-assigned unique identifier for each school feature
- **OBJECTID**: Object identifier
- **NCESID**: National Center for Education Statistics ID (12-digit unique identifier)
- **NAME**: Name of the school
- **ADDRESS**: Street address
- **CITY**: City where the school is located
- **STATE**: Two-letter state abbreviation (e.g., "CA", "NY")
- **ZIP**: 5-digit ZIP code
- **ZIP4**: 4-digit ZIP code extension
- **TELEPHONE**: School phone number
- **TYPE**: Type of school (single character code)
- **STATUS**: Operational status (single character code)
- **POPULATION**: Population of the area served
- **COUNTY**: County name
- **COUNTYFIPS**: County FIPS code
- **COUNTRY**: Country code (typically "USA")
- **LATITUDE**: Latitude coordinate
- **LONGITUDE**: Longitude coordinate
- **NAICS_CODE**: North American Industry Classification System code
- **NAICS_DESC**: NAICS description
- **SOURCE**: Data source
- **SOURCEDATE**: Date when source data was collected
- **VAL_METHOD**: Validation method
- **VAL_DATE**: Validation date
- **WEBSITE**: School website URL
- **LEVEL_**: School level (e.g., "ELEMENTARY", "MIDDLE", "HIGH")
- **ENROLLMENT**: Number of students enrolled
- **ST_GRADE**: Starting grade (e.g., "PK", "KG", "01", "09")
- **END_GRADE**: Ending grade (e.g., "05", "08", "12")
- **DISTRICTID**: School district identifier (7-digit code)
- **FT_TEACHER**: Number of full-time teachers
- **SHELTER_ID**: Emergency shelter identifier (if applicable)

## When to Use

Use this skill to:

- Find schools by name or location
- Find all schools in a specific city, county, or state
- Query schools by level (elementary, middle, high school)
- Find schools by enrollment size
- Find schools serving specific grade ranges
- Analyze school distribution and accessibility
- Find schools within a geographic area
- Query schools by district

## How to Use

### Step 1: Import Required Libraries

```python
import geopandas as gpd
import requests
```

### Step 2: Define the Query Function

Use the `get_features` function to query the feature service. The **bbox parameter** is crucial for spatial filtering.

**IMPORTANT**: This service has a maximum record count of 2000. For queries that may return more than 2000 results, you'll need to implement pagination using the `resultOffset` parameter.

```python
def get_features(service_url, where, bbox=None, max_records=2000):
    """
    Query the ArcGIS Feature Service for public schools.
    
    Parameters:
    -----------
    service_url : str
        The URL of the ArcGIS Feature Service
    where : str
        SQL-like WHERE clause to filter features
    bbox : list or tuple, optional
        Bounding box as [minx, miny, maxx, maxy] in WGS84 (EPSG:4326)
        Default is the continental USA bounds
    max_records : int, optional
        Maximum number of records to return (default: 2000, which is the service limit)
    
    Returns:
    --------
    geopandas.GeoDataFrame
        GeoDataFrame containing the queried public school features in EPSG:4326
    """
    
    # Default to continental USA bounds if no bbox provided
    if bbox is None:
        bbox = [-125.0, 24.396308, -66.93457, 49.384358]
    
    minx, miny, maxx, maxy = bbox
    
    params = {
        "where": where,
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "outSR": "4326",
        "resultOffset": 0,
        "resultRecordCount": min(max_records, 2000)  # Service max is 2000
    }
    
    response = requests.get(service_url + "/query", params=params)
    data = response.json()
    
    if data.get('features'):
        return gpd.GeoDataFrame.from_features(data['features'], crs="EPSG:4326")
    else:
        return gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")
```

### Step 3: Query Examples

#### Example 1: Find Schools in a Specific City

```python
url = "https://services5.arcgis.com/HDRa0B57OVrv2E1q/ArcGIS/rest/services/Public_Schools/FeatureServer/0"

# Query for schools in Denver
where = "CITY = 'DENVER' AND STATE = 'CO'"
denver_schools = get_features(url, where)

print(f"Found {len(denver_schools)} schools in Denver")
print(denver_schools[['NAME', 'LEVEL_', 'ENROLLMENT']].head())
```

#### Example 2: Find Elementary Schools in a State

```python
# California bounding box
california_bbox = [-124.48, 32.53, -114.13, 42.01]

# Query for elementary schools in California
where = "STATE = 'CA' AND LEVEL_ = 'ELEMENTARY'"
ca_elementary = get_features(url, where, bbox=california_bbox)

print(f"Found {len(ca_elementary)} elementary schools in California")
```

#### Example 3: Find High Schools in a County

```python
# Query for high schools in Los Angeles County
where = "COUNTY = 'LOS ANGELES' AND LEVEL_ = 'HIGH'"
la_high_schools = get_features(url, where)

print(f"Found {len(la_high_schools)} high schools in Los Angeles County")
```

#### Example 4: Find Large Schools (by Enrollment)

```python
# Find schools with 1000 or more students
where = "ENROLLMENT >= 1000"
large_schools = get_features(url, where)

print(f"Found {len(large_schools)} schools with 1000+ students")
print(large_schools[['NAME', 'CITY', 'STATE', 'ENROLLMENT']].sort_values('ENROLLMENT', ascending=False).head(10))
```

#### Example 5: Find Schools by Grade Range

```python
# Find schools serving grades 9-12 (typical high schools)
where = "ST_GRADE = '09' AND END_GRADE = '12'"
traditional_high_schools = get_features(url, where)

print(f"Found {len(traditional_high_schools)} traditional high schools (grades 9-12)")
```

#### Example 6: Find Schools with Pre-K Programs

```python
# Find schools starting with Pre-K
where = "ST_GRADE = 'PK'"
prek_schools = get_features(url, where)

print(f"Found {len(prek_schools)} schools with Pre-K programs")
```

#### Example 7: Find Schools by Name

```python
# Find schools with "Lincoln" in the name
where = "NAME LIKE '%LINCOLN%'"
lincoln_schools = get_features(url, where)

print(f"Found {len(lincoln_schools)} schools with 'Lincoln' in the name")
```

#### Example 8: Find Middle Schools in a District

```python
# Query for middle schools (grades 6-8 typical)
# Note: DISTRICTID format should be verified from actual data
where = "LEVEL_ = 'MIDDLE'"
middle_schools = get_features(url, where)

print(f"Found {len(middle_schools)} middle schools")
```

## Notes

The service has a maximum record count of 2000. If your query returns more results, you'll need to use pagination or refine your query with a more specific WHERE clause or smaller bbox.

### Understanding the bbox Parameter

The **bbox (bounding box) parameter** is essential for efficient spatial queries:

- **Format**: `[minx, miny, maxx, maxy]` in WGS84 coordinates (longitude, latitude)
- **Purpose**: Limits the geographic extent of the query, reducing response time and data volume
- **Default**: If not provided, defaults to continental USA bounds
- **Use case**: Always provide a bbox when querying for schools in a specific region

**Why bbox matters**: Without a bbox, the service may return all schools matching the WHERE clause across the entire USA, which could exceed the 2000 record limit. The bbox acts as a spatial pre-filter, dramatically improving query performance.

**Common City/State Bounding Boxes**:
```python
# New York City
nyc_bbox = [-74.26, 40.49, -73.70, 40.92]

# Los Angeles
la_bbox = [-118.67, 33.70, -118.16, 34.34]

# Chicago
chicago_bbox = [-87.94, 41.64, -87.52, 42.02]

# Denver
denver_bbox = [-105.11, 39.61, -104.87, 39.91]

# Miami
miami_bbox = [-80.32, 25.71, -80.13, 25.86]

# California
california_bbox = [-124.48, 32.53, -114.13, 42.01]

# Texas
texas_bbox = [-106.65, 25.84, -93.51, 36.50]

# Florida
florida_bbox = [-87.63, 24.52, -80.03, 31.00]
```

### Using the STATE Field

The `STATE` field contains two-letter state abbreviations:

- **Format**: Uppercase two-letter codes (e.g., "CA", "NY", "TX")
- **Query pattern**: Use exact match with state abbreviation
  - Example: `"STATE = 'CA'"` for California
  - Example: `"STATE = 'NY'"` for New York
- **Multiple states**: Use OR to find schools in multiple states
  - Example: `"STATE = 'CA' OR STATE = 'OR' OR STATE = 'WA'"`

### Using the LEVEL_ Field

Filter by school level:

- **Common values**:
  - `"ELEMENTARY"` - Elementary schools (typically K-5 or K-6)
  - `"MIDDLE"` - Middle schools (typically 6-8 or 7-8)
  - `"HIGH"` - High schools (typically 9-12)
  - May also include: `"PREKINDERGARTEN"`, `"ADULT EDUCATION"`, `"UNGRADED"`, etc.
- **Query patterns**:
  - Example: `"LEVEL_ = 'ELEMENTARY'"`
  - Example: `"LEVEL_ = 'HIGH'"`
  - Example: `"LEVEL_ LIKE '%MIDDLE%'"` for partial matches

### Using Grade Range Fields (ST_GRADE and END_GRADE)

Filter by specific grade ranges:

- **Format**: Two-character codes
  - Pre-K: `"PK"`
  - Kindergarten: `"KG"`
  - Grades 1-9: `"01"` through `"09"`
  - Grades 10-12: `"10"`, `"11"`, `"12"`
- **Query patterns**:
  - Elementary (K-5): `"ST_GRADE = 'KG' AND END_GRADE = '05'"`
  - Middle (6-8): `"ST_GRADE = '06' AND END_GRADE = '08'"`
  - High (9-12): `"ST_GRADE = '09' AND END_GRADE = '12'"`
  - Schools with Pre-K: `"ST_GRADE = 'PK'"`

### Using the ENROLLMENT Field

Filter by school size:

- **Format**: Integer (number of students)
- **Query patterns**:
  - Large schools: `"ENROLLMENT >= 1000"`
  - Medium schools: `"ENROLLMENT BETWEEN 500 AND 999"`
  - Small schools: `"ENROLLMENT < 500"`
  - Sort by size: Use `.sort_values('ENROLLMENT', ascending=False)` in pandas
  - Filter out schools with no enrollment data: `"ENROLLMENT IS NOT NULL"`

### Using the FT_TEACHER Field

Filter by teacher count:

- **Format**: Integer (number of full-time teachers)
- **Query patterns**:
  - Schools with many teachers: `"FT_TEACHER >= 50"`
  - Calculate student-teacher ratio: `ENROLLMENT / FT_TEACHER` in pandas
  - Example: `"FT_TEACHER IS NOT NULL AND ENROLLMENT IS NOT NULL"`

### Using the TYPE and STATUS Fields

Note: These are single-character codes. You may need to query the data to determine the exact values:

- **TYPE field**: Single character code for school type
- **STATUS field**: Single character code for operational status
- **Query pattern**: Use exact match
  - Example: `"STATUS = '1'"` (if '1' means open/active)
  - Example: `"TYPE = 'R'"` (meaning depends on data)

### WHERE Clause Tips

- Use uppercase for STATE field: `"STATE = 'CA'"` not `"STATE = 'ca'"`
- Use LIKE for partial name matches: `"NAME LIKE '%ELEMENTARY%'"`
- For LEVEL_, use exact match or LIKE: `"LEVEL_ = 'ELEMENTARY'"` or `"LEVEL_ LIKE '%HIGH%'"`
- Use proper grade codes: `"ST_GRADE = 'PK'"` for Pre-K, `"ST_GRADE = 'KG'"` for Kindergarten
- Combine multiple conditions with AND / OR:
  - Example: `"STATE = 'CA' AND LEVEL_ = 'HIGH' AND ENROLLMENT >= 500"`
- Use numeric comparisons for ENROLLMENT and FT_TEACHER:
  - Example: `"ENROLLMENT >= 500"`
- Filter out null values when needed:
  - Example: `"ENROLLMENT IS NOT NULL"`
- Always enclose string values in single quotes
- Use `1=1` to match all features when relying solely on spatial filtering (bbox)
- Remember the 2000 record limit - use bbox and specific WHERE clauses

### Handling the 2000 Record Limit

If you expect more than 2000 results (e.g., all elementary schools in California), implement pagination:

```python
def get_all_features(service_url, where, bbox=None):
    """
    Get all features, handling pagination for >2000 results.
    """
    all_features = []
    offset = 0
    batch_size = 2000
    
    if bbox is None:
        bbox = [-125.0, 24.396308, -66.93457, 49.384358]
    
    minx, miny, maxx, maxy = bbox
    
    while True:
        params = {
            "where": where,
            "geometry": f"{minx},{miny},{maxx},{maxy}",
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": "4326",
            "resultOffset": offset,
            "resultRecordCount": batch_size
        }
        
        response = requests.get(service_url + "/query", params=params)
        data = response.json()
        
        if not data.get('features'):
            break
            
        all_features.extend(data['features'])
        
        if len(data['features']) < batch_size:
            break
            
        offset += batch_size
    
    if all_features:
        return gpd.GeoDataFrame.from_features(all_features, crs="EPSG:4326")
    else:
        return gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")
```

### Complete Example: Analyze Schools in a District

```python
import geopandas as gpd
import requests
import matplotlib.pyplot as plt

# Function definition (as above)
def get_features(service_url, where, bbox=None, max_records=2000):
    if bbox is None:
        bbox = [-125.0, 24.396308, -66.93457, 49.384358]
    
    minx, miny, maxx, maxy = bbox
    
    params = {
        "where": where,
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "outSR": "4326",
        "resultOffset": 0,
        "resultRecordCount": min(max_records, 2000)
    }
    
    response = requests.get(service_url + "/query", params=params)
    data = response.json()
    
    if data.get('features'):
        return gpd.GeoDataFrame.from_features(data['features'], crs="EPSG:4326")
    else:
        return gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")

# Query for schools in Denver
url = "https://services5.arcgis.com/HDRa0B57OVrv2E1q/ArcGIS/rest/services/Public_Schools/FeatureServer/0"
denver_bbox = [-105.11, 39.61, -104.87, 39.91]
where = "CITY = 'DENVER' AND STATE = 'CO'"

denver_schools = get_features(url, where, bbox=denver_bbox)

# Display results
print(f"Found {len(denver_schools)} schools in Denver\n")

# Schools by level
if 'LEVEL_' in denver_schools.columns:
    print("Schools by level:")
    print(denver_schools['LEVEL_'].value_counts())

# Enrollment statistics
if 'ENROLLMENT' in denver_schools.columns:
    enrolled = denver_schools[denver_schools['ENROLLMENT'].notna()]
    print(f"\nEnrollment statistics:")
    print(f"  Total students: {enrolled['ENROLLMENT'].sum():,.0f}")
    print(f"  Average enrollment: {enrolled['ENROLLMENT'].mean():.0f}")
    print(f"  Largest school: {enrolled['ENROLLMENT'].max():.0f} students")
    print(f"  Smallest school: {enrolled['ENROLLMENT'].min():.0f} students")

# Teacher statistics
if 'FT_TEACHER' in denver_schools.columns:
    teachers = denver_schools[denver_schools['FT_TEACHER'].notna()]
    print(f"\nTeacher statistics:")
    print(f"  Total full-time teachers: {teachers['FT_TEACHER'].sum():,.0f}")
    
    # Calculate student-teacher ratio
    ratio_data = denver_schools[(denver_schools['ENROLLMENT'].notna()) & 
                                 (denver_schools['FT_TEACHER'].notna()) &
                                 (denver_schools['FT_TEACHER'] > 0)]
    if len(ratio_data) > 0:
        ratio_data['ratio'] = ratio_data['ENROLLMENT'] / ratio_data['FT_TEACHER']
        print(f"  Average student-teacher ratio: {ratio_data['ratio'].mean():.1f}:1")

# Top 5 largest schools
if 'ENROLLMENT' in denver_schools.columns:
    print("\nTop 5 largest schools by enrollment:")
    top5 = denver_schools.nlargest(5, 'ENROLLMENT')[['NAME', 'LEVEL_', 'ENROLLMENT']]
    for idx, row in top5.iterrows():
        print(f"  {row['NAME']} ({row['LEVEL_']}): {row['ENROLLMENT']:.0f} students")

# Grade range distribution
if 'ST_GRADE' in denver_schools.columns and 'END_GRADE' in denver_schools.columns:
    grade_ranges = denver_schools.groupby(['ST_GRADE', 'END_GRADE']).size()
    print(f"\nCommon grade ranges:")
    for (start, end), count in grade_ranges.nlargest(5).items():
        print(f"  Grades {start}-{end}: {count} schools")

# Plot schools by level
fig, ax = plt.subplots(figsize=(12, 10))

if 'LEVEL_' in denver_schools.columns:
    # Color code by school level
    denver_schools.plot(ax=ax, column='LEVEL_', legend=True, markersize=50, 
                        alpha=0.7, categorical=True, cmap='Set1')
else:
    denver_schools.plot(ax=ax, markersize=50, alpha=0.7, color='blue')

ax.set_title('Public Schools in Denver, Colorado')
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
plt.tight_layout()
plt.show()
```
