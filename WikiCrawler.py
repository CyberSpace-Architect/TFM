import argparse
from datetime import datetime, timedelta

import pywikibot

"""
    FUNCIONALIDADES
        1º Búsqueda general nivel edit-war basado en criterio de todos los artículos del set

        2º Búsqueda relacionada con artículo del set
            --> Mostrar set de categorías asociadas
                --> Buscar artículos por categoría
                    --> Seleccionar cuales añadir
                    --> Volver
                --> Volver

        3º Búsqueda por palabras clave (artículos o categorías)

        4º Consultar información específica edit-war de un artículo del set
            - Nivel de edit-war basado en criterio
            - Página de discusión --> url y nº de cambios
                --> Por definir: Opciones análisis en profundidad (contenido, usuarios, localizacion, contenido polémico concreto...)
            - Página de historial --> url y nº de cambios
                --> Por definir: Opciones análisis en profundidad (contenido, usuarios, localizacion...)

        5º Añadir artículo al set
                
        6º Eliminar artículo del set
"""


def parse_wiki_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("search_query",
                        help="Query used to search related pages in Wikipedia")
    parser.add_argument("-l", "--search_limit", nargs=1, type=int,
                        help="Set a limit to the number of result pages to return (default no limit)",)
    parser.add_argument("-r", "--time_range", nargs=2, metavar=("START_DATE", "END_DATE"),
                        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
                        help="Specify time range (use date in YYYY-MM-DD format) to check for edit-wars (default from 30 days ago until now)")


    return parser.parse_args()


def crawl(search, search_limit, time_range):
    if search_limit is not None:
        search_limit = search_limit[0]
    if time_range is not None:
        start_date, end_date = time_range
    else:
        start_date = datetime.now().replace(microsecond=0) - timedelta(days=30)
        end_date = datetime.now().replace(microsecond=0)

    site = pywikibot.Site('es', 'wikipedia')

    pages = site.search(search, total=search_limit)    # Buscar artículos por titulo
    #pages = pywikibot.Page(site, search).categories()  # Buscar categorías asociadas a un artículo
    #pages = pywikibot.Category(site, search).articles()     # Buscar artículos por categoría # Categoría:Eventos políticos en curso
    #pages = pywikibot.Category(site, search).subcategories()    # Buscar subcategorías por categoría (no merece mucho la pena)

    idx = 0

    print(f'\n[ID] PAGE TITLE --> URL\n')

    for page in pages:
        idx += 1
        print(f'[{idx}] {page.title()} --> {page.full_url()}')

        """ # Discussion page changes within time range
        discussion_page = page.toggleTalkPage()
        discussion_page_revs = revisions_within_range(discussion_page, start_date, end_date)
        print(f'\n\tDiscussion page changes (from {start_date} to {end_date}): {len(discussion_page_revs)}')
        print_revs(discussion_page_revs)

        # History revisions page changes within time range
        history_page_revs = revisions_within_range(page, start_date, end_date)
        print(f'\tHistory page changes (from {start_date} to {end_date}): {len(history_page_revs)}')
        print_revs(history_page_revs)"""

    print(f'\nResults found: {idx}')

    return pages

def search_results_options(pages):
    None


def revisions_within_range(page, start_date, end_date):

    result_revs = []

    # Get history page and create iterator
    revs = page.revisions(reverse=False, total=None)
    it = iter(revs)
    rev = next(it, None)

    # Prepare time range
    limit_date = datetime.now() - timedelta(days=30)
    if rev is not None:
        rev_date = rev.timestamp

        while rev is not None and rev_date > end_date:
            rev = next(it, None)
            if rev is not None:
                rev_date = rev.timestamp

        if rev is not None:
            while rev is not None and rev_date > start_date:
                result_revs.append(rev)

                rev = next(it, None)
                if rev is not None:
                    rev_date = rev.timestamp

    return result_revs

def print_revs(rev_array):
    print(f'\n\t\tREV ID, TIMESTAMP, USER')
    for rev in rev_array:
        print(f'\t\t{rev.revid}, {rev.timestamp}, {rev.user}')
    print(f'')


