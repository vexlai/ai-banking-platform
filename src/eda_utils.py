"""Entrada programática del EDA; la ejecución revisable está en notebooks/02_eda.ipynb."""
from src.eda_core import start, finish
from src import eda_readiness as ready, eda_domains as domain, eda_outputs as output


def run_eda():
    con, context = start()
    try:
        ready.semantic(con)
        ready.temporal(con)
        domain.customers_products(con, context)
        domain.transactions(con, context)
        domain.digital(con, context)
        domain.service(con, context)
        domain.transcripts(con)
        domain.complaints(con, context)
        domain.satisfaction(con, context)
        domain.campaigns(con, context)
        domain.branches(con)
        ready.exchange(con)
        output.customer360(con, context)
        output.figures()
        output.findings(context)
        finish(con, context)
        return context
    finally:
        con.close()
