from WikiCrawler import WikiCrawler

def main():
    wiki_crawler = WikiCrawler()

    wiki_crawler.exec()


if __name__ == "__main__":
    main()











    """
        FUNCIONALIDADES
            1º Búsqueda por palabras clave (artículos o ¿categorías?)

            2º Búsqueda relacionada con artículo del set
                --> Mostrar set de categorías asociadas
                    --> Buscar artículos por categoría
                        --> Seleccionar cuales añadir
                        --> Volver
                    --> Volver
                --> Volver

            3º Búsqueda general nivel edit-war basado en criterio de todos los artículos del set

            4º Consultar información específica edit-war de un artículo del set
                - Nivel de edit-war basado en criterio
                - Página de discusión --> url y nº de cambios
                    --> Por definir: Opciones análisis en profundidad (contenido, usuarios, localizacion, contenido polémico concreto...)
                - Página de historial --> url y nº de cambios
                    --> Por definir: Opciones análisis en profundidad (contenido, usuarios, localizacion...)

            5º Eliminar artículo del set

            6º Salir
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            Detección, necesito sacar:
            1º) Recorrer las revisiones calculandos sus fuzzy_hashes para detectar los reverts --> 
                Lista de revert y hash 
            2º) Recorrer la lista de (revert, hash) para detectar los mutual reverts --> 
                Lista de mutual reverts y hashes (tupla de tuplas)
            3º) Recorrer la lista de mutual reverts, calculando para cada usuario el nº total de ediciones que ha hecho 
            en el articulo y guardando el minimo (Nr) --> 
                Diccionario de usuarios mutual reverters (usuario, nº ediciones) y 
                Lista de valores Nr (Cuidado con los self-reverts no contarlos)
            4º) Eliminar de los calculos al par de editores que dé el valor máximo -->
                Buscar máximo lista de valores Nr y quitarlo
            5º) Sacar el nº de usuarios que han hecho reverts mutuos (cuidado de no contarlos más de 1 vez) -->
                Sumar tamaño Diccionario de usuarios mutual reverters (E)
           
            6º) Sumar todos los valores de la lista y multiplicar por E
    """







