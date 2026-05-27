from rq import Queue
from redis import Redis
from services.maps_service import buscar_maps
from services.serp_service import enriquecer_serp
from app import salvar_historico, carregar_historico

redis_conn = Redis()
fila = Queue(connection=redis_conn)


def processar_busca(atividade, cidade, chave):
    historico = carregar_historico()

    empresas = buscar_maps(atividade, cidade, limite=20, enriquecer=True)

    for empresa in empresas:
        if not empresa.get("telefone") or not empresa.get("instagram"):
            dados = enriquecer_serp(empresa["nome"], cidade)

            if not empresa.get("instagram"):
                empresa["instagram"] = dados.get("instagram")

            if not empresa.get("telefone"):
                empresa["telefone"] = dados.get("telefone_extra")

    historico[chave] = empresas
    salvar_historico(historico)