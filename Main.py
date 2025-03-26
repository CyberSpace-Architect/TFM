import argparse

from WikiCrawler import *

def main():
    exit_opt = False

    args = parse_wiki_arguments()

    #startDate = datetime.now().replace(microsecond=0) - timedelta(days=30)
    #endDate = datetime.now().replace(microsecond=0)

    pages = crawl(args.search_query, args.search_limit, args.time_range)

    # Print search set help and allow options

if __name__ == "__main__":
    main()






