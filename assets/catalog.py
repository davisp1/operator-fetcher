#!/bin/python3

import os
import re
import logging
import json
import psycopg2
import traceback
from string import Template

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')

# Create another handler that will redirect log entries to STDOUT
STDOUT_HANDLER = logging.StreamHandler()
STDOUT_HANDLER.setLevel(logging.DEBUG)
STDOUT_HANDLER.setFormatter(formatter)
LOGGER.addHandler(STDOUT_HANDLER)

# Path to fetch operators repositories
FETCH_OP_PATH = "fetch-op"

# Path to prepared operators
OP_PATH = "op"

# Families definition
FAMILIES = [
    ('Data_Exploration', 'Functions exploring the data: searches, highlights some elements, ...', 'Data Exploration'),
    ('Stats__TS_Correlation_Computation', 'Set of correlation functions, applied on Time series', 'Stats/Ts Correlation Computation'),
    ('Stats__TS_Stats', 'Set of functions about statistics features on Time series', 'Stats/Statistics On Ts'),
    ('Preprocessing_TS__Reduction', 'Set of pre-processing functions which reduce information of Time series', 'Pre-Processing On Ts/Reduction'),
    ('Preprocessing_TS__Cleaning', 'Set of pre-processing functions which are cleaning the information of Time series.', 'Pre-Processing On Ts/Cleaning'),
    ('Preprocessing_TS__Transforming', 'Set of pre-processing functions which are transforming the Time series: not classified as cleaning, or reduction functions.', 'Pre-Processing On Ts/Transforming'),
    ('Data_Modeling__Supervised_Learning', 'Supervised learning', 'Data Modeling/Supervised Learning'),
    ('Data_Modeling__Unsupervised_Learning', 'Collection of Unsupervised learning agorithms', 'Data Modeling/Unsupervised Learning'),
    ('Undefined', 'Family for algorithms with wrong or undefined family', 'Undefined')]

insert_family = Template("""
INSERT INTO catalogue_functionalfamilydao
("name", "desc", "label")
VALUES
  ('$name', '$description', '$label');
""")

algorithm = Template("""
INSERT INTO catalogue_algorithmdao
("name", "label", "desc", "family_id")
VALUES 
  ('$name', '$label', '$description', (SELECT id FROM catalogue_functionalfamilydao WHERE name = '$family'));
""")

implementation = Template("""
INSERT INTO catalogue_implementationdao
("name", "label", "desc", "algo_id", "execution_plugin", "library_address", "visibility")
VALUES
  ('$name', '$label', '$description', (SELECT id FROM catalogue_algorithmdao WHERE name = '$name'), 'apps.algo.execute.models.business.python_local_exec_engine::PythonLocalExecEngine', '$entry_point', '$visibility');
""")

profile_item_IN = Template("""
INSERT INTO catalogue_profileitemdao
("name", "label", "desc", "direction", "dtype", "order_index", "data_format")
VALUES
  ('$name', '$label', '$description', $direction, $dtype, $index, '$type');
INSERT INTO catalogue_implementationdao_input_desc_items ("implementationdao_id", "profileitemdao_id")
VALUES
   ((SELECT id FROM catalogue_implementationdao WHERE "name" = '$name_algo'), 
    (SELECT id FROM catalogue_profileitemdao WHERE "name" = '$name'));
""")

profile_item_PARAM = Template("""
INSERT INTO catalogue_profileitemdao
("name", "label", "desc", "direction", "dtype", "order_index", "data_format", "domain_of_values", "default_value")
VALUES
  ('$name', '$label', '$description', $direction, $dtype, $index, '$type', '$domain', '$default_value');
INSERT INTO catalogue_implementationdao_input_desc_items ("implementationdao_id", "profileitemdao_id")
VALUES
   ((SELECT id FROM catalogue_implementationdao WHERE "name" = '$name_algo'), 
    (SELECT id FROM catalogue_profileitemdao WHERE "name" = '$name'));
""")

profile_item_OUT = Template("""
INSERT INTO catalogue_profileitemdao
("name", "label", "desc", "direction", "dtype", "order_index", "data_format")
VALUES
  ('$name', '$label', '$description', $direction, $dtype, $index, '$type');
INSERT INTO catalogue_implementationdao_output_desc_items ("implementationdao_id", "profileitemdao_id")
VALUES
   ((SELECT id FROM catalogue_implementationdao WHERE name = '$name_algo'), 
    (SELECT id FROM catalogue_profileitemdao WHERE "name" = '$name'));
""")


def extract_catalog(op_name):
    """
    Retrieves list of catalog_def for given operator
    """
    catalog_list = []

    # Check if catalog definition is present in repository
    pattern = re.compile("catalog_def(_[0-9]{,2})?.json")
    for file_path in os.listdir("fetch-op/op-%s" % op_name):
        if pattern.match(file_path):
            with open("%s/op-%s/%s" % (FETCH_OP_PATH, op_name, file_path)) as cat_def:
                catalog_list.append(json.load(cat_def))

    return catalog_list


def format_catalog(catalog):
    """
    Add missing optional keys with default values in catalog
    """
    # create optional keys with default values if missing
    if 'family' not in catalog or catalog['family'] not in [x[0] for x in FAMILIES]:
        catalog['family'] = 'Uncategorized'
    if 'label' not in catalog:
        catalog['label'] = catalog['name']
    if 'description' not in catalog:
        catalog['description'] = catalog['name']
    else:
        # Double quotes in description to agree sql requests
        catalog['description'] = catalog.get('description').replace("'", "''")

    def format_item(item):
        # create optional keys with default values if missing
        if 'label' not in item:
            item['label'] = item['name']
        else:
            # Double quotes in description to agree sql requests
            item['label'] = item.get('label').replace("'", "''")
        if 'description' not in item:
            item['description'] = item['name']
        else:
            # Double quotes in description to agree sql requests
            item['description'] = item.get('description').replace("'", "''")

    if 'inputs' in catalog:
        for input in catalog.get('inputs'):
            format_item(input)
    if 'outputs' in catalog:
        for output in catalog.get('outputs'):
            format_item(output)
    if 'parameters' in catalog:
        for parameter in catalog.get('parameters'):
            format_item(parameter)
            if 'domain' not in parameter:
                parameter['domain'] = None
            else:
                # Double quotes in description to agree sql requests
                if type(parameter.get('domain')) is list:
                    parameter['domain'] = str(parameter.get('domain')).replace("'", "''")
                else:
                    # string case
                    parameter['domain'] = parameter.get('domain').replace("'", "''")
            if 'default_value' not in parameter:
                parameter['default_value'] = None

    return catalog


def catalog_json_to_SQL(catalog):
    """
    Convert algorithm catalog definition from json to sql request
    """
    sql = algorithm.substitute(catalog)
    catalog['entry_point'] = '{}.{}'.format('ikats.algo', catalog.get('entry_point'))
    sql += implementation.substitute(catalog, visibility=catalog.get('visibility') if 'visibility' in catalog else True)
    index_profileitem = 0
    if 'inputs' in catalog:
        for input in catalog.get('inputs'):
            sql += profile_item_IN.substitute(input,
                                              name='{}_{}_{}'.format('input_', catalog.get('name'), input.get('name')),
                                              direction=0,
                                              dtype=1,
                                              index=index_profileitem,
                                              name_algo=catalog.get('name'))
            index_profileitem += 1
    if 'parameters' in catalog:
        for parameter in catalog.get('parameters'):
            sql += profile_item_PARAM.substitute(parameter,
                                                 name='{}_{}_{}'.format('output_', catalog.get('name'),
                                                                        parameter.get('name')),
                                                 direction=0,
                                                 dtype=0,
                                                 index=index_profileitem,
                                                 name_algo=catalog.get('name'))
            index_profileitem += 1
    if 'outputs' in catalog:
        for output in catalog.get('outputs'):
            sql += profile_item_OUT.substitute(output,
                                               name='{}_{}_{}'.format('parameter_', catalog.get('name'),
                                                                      output.get('name')),
                                               direction=1,
                                               dtype=1,
                                               index=index_profileitem,
                                               name_algo=catalog.get('name'))
            index_profileitem += 1

    return sql.replace("\'None\'", "NULL")


def delete_catalog_postgres():
    """
    Delete data from catalogue databases
    """
    CATALOG_DATABASES_LIST = [
        'catalogue_implementationdao_input_desc_items', 'catalogue_implementationdao_output_desc_items',
        'catalogue_profileitemdao',
        'catalogue_implementationdao', 'catalogue_algorithmdao', 'catalogue_functionalfamilydao']
    for db in CATALOG_DATABASES_LIST:
        request_to_postgres("DELETE from %s" % db)


def populate_catalog_families():
    """
    Insert families in catalog
    """
    for family in FAMILIES:
        sql = insert_family.substitute(name=family[0], description=family[1], label=family[2])
        request_to_postgres(sql)

def request_to_postgres(request):
    """
    request postgresql with sql requests as a string
    """
    conn_string = "host='127.0.0.1' dbname='ikats' user='ikats' password='ikats' port='5432'"
    connection = None
    try:
        connection = psycopg2.connect(conn_string)
        cursor = connection.cursor()
        cursor.execute(request)
        connection.commit()
        cursor.close()
    except Exception as error:
        LOGGER.error(error)
    finally:
        if connection is not None:
            connection.close()


def process_operator_catalog(repo):
    """
    Processing the catalog for a given operator
    """

    # extract catalog from catalog_def.json in given repo
    catalog_list_json = extract_catalog(repo)

    if catalog_list_json:
        for catalog_json in catalog_list_json:
            format_catalog(catalog_json)

            # generate SQL request from catalog definition in JSON format
            sql = catalog_json_to_SQL(catalog_json)

            # postgresql request
            request_to_postgres(sql)
