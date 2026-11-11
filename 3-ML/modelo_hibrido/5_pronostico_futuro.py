# %% [markdown]
# # Versión 3 — predicciones completas (sin huecos) y pronóstico h1–h3 desde el último día con datos
#
# 1. Componente final "F2c_hc": F2c_h (híbrido elegido en validación, w >= 0,05) donde tiene pronóstico; en los
#    orígenes que F2c_h no cubre (ventanas con muchos días sin medición) se completa con F2c_r (mismo híbrido
#    entrenado con la serie rellenada). Regla por disponibilidad de datos, no por la prueba.
# 2. Pronóstico desde el último día con medición (L): los días L+1..L+3 se tratan como días sin medición
#    (mediana del mismo mes del entrenamiento, como el relleno del dataset). Se reentrena la LSTM de F2c_r con la
#    misma semilla (reproduce sus predicciones guardadas), se guarda como lstm_rellenada_B.keras y se combina con
#    Prophet ajustado con los datos hasta L, con el w y la corrección de Duan de F2c_r elegidos en validación.
# Salidas: modelos/<estación>/F2c_hc.pkl, version_final/modelos/<estación>/lstm_rellenada_{A,B}.keras,
#          version_final/modelos/<estación>/pronostico_futuro.csv
# Ejecutar por fuente (correr_A15.bat): WAYRA_FUENTE=combinada y WAYRA_FUENTE=pasco_moquegua.

# %%
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("modelo_hibrido"))
import wayra_comun as wc
import wayra_prophet as wp
import wayra_lstm as wl
import wayra_hibrido as wh
import motor as mt
import v3_entradas as ve

warnings.filterwarnings("ignore")
BASE = os.path.join(wc.RAIZ, "modelo_hibrido")
wl.MIN_FRACCION_OBSERVADA = 0.0
_futuro_original = mt.futuro_externo
LLAVE = ["origen", "horizonte"]

for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    est = cfg["estacion"]
    destino = os.path.join(BASE, "version_final", "modelos", est)
    os.makedirs(destino, exist_ok=True)

    # --- 1. componente final sin huecos
    h_ = pd.read_pickle(os.path.join(BASE, "modelos", est, "F2c_h.pkl"))
    r_ = pd.read_pickle(os.path.join(BASE, "modelos", est, "F2c_r.pkl"))
    a = h_["pred"].dropna(subset=["valor"])
    b = r_["pred"].dropna(subset=["valor"])
    falta = ~pd.MultiIndex.from_frame(b[LLAVE]).isin(pd.MultiIndex.from_frame(a[LLAVE]))
    comp = pd.concat([a.assign(fuente_componente="F2c_h"), b[falta].assign(fuente_componente="F2c_r")], ignore_index=True)
    comp = comp.sort_values(["horizonte", "origen"]).reset_index(drop=True)
    comp["variante"] = "F2c_hc"
    pd.to_pickle({"pred": comp, "info": {**h_["info"], "esquema": "F2c_hc", "completado_con": "F2c_r",
                                         "eleccion_val_completado": r_["info"]["eleccion_val"]}},
                 os.path.join(BASE, "modelos", est, "F2c_hc.pkl"))
    print(f"{est}: F2c_hc = {len(a)} pronósticos de F2c_h + {int(falta.sum())} de F2c_r", flush=True)

    # --- 2. pronóstico desde el último día con medición
    ds = wc.cargar_dataset(clave)
    L = ds["OBJETIVO"].last_valid_index()
    futuras = pd.date_range(L + pd.Timedelta(days=1), periods=len(wc.HORIZONTES))
    ds = ds.reindex(ds.index.union(futuras))
    if cfg["regimen"]:
        ds["OPERACION_CAUSAL"] = ds["OPERACION_CAUSAL"].ffill()
    # días futuros en el dataset de entrada: sin medición -> mediana del mismo mes del entrenamiento
    d = ve.DATASET[ve.DATASET["estacion"] == est]
    tr = d[(d["PARTICION"] == "train") & (d["relleno_tipo"].isin(["observado", "estacion_vecina"]))]
    nuevas = pd.DataFrame(index=futuras.difference(d.index))
    if len(nuevas):
        nuevas["estacion"] = est
        nuevas["OBJETIVO"] = [tr["OBJETIVO"][tr.index.month == f.month].median() for f in nuevas.index]
        nuevas["relleno_tipo"] = "climatologia_mensual_train"
        for c in ("intensidad_operacion_FUGA", "actividad_industrial_FUGA", "estado_operacion_FUGA"):
            nuevas[c] = d[c].ffill().iloc[-1]
        ve.DATASET = pd.concat([ve.DATASET, nuevas])
    fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
    D = {"clave": clave, "cfg": cfg, "ds": ds, "est": est, "tag": est, "fin_train": fin_train,
         "fin_val": pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1), "carpeta": destino}
    oficial = pd.read_pickle(os.path.join(wc.RAIZ, "experimento_2", "modelos", est, "E9opt.pkl"))
    p, fuente = oficial["info"]["params"], oficial["info"]["fuente_meteo"]
    v = mt.variables_base(D, ve.extras(est, ds.index))
    rel = ve.DATASET[ve.DATASET["estacion"] == est]
    rel = rel[~rel.index.duplicated(keep="first")].reindex(ds.index)
    v["y_log"] = np.log1p(rel["OBJETIVO"])
    v["y_falta"] = (rel["relleno_tipo"] == "climatologia_mensual_train").astype(float)
    wl.fijar_semillas_keras()
    fut, inicio = ve.futuro(D, "F2c", fuente, _futuro_original)
    M = mt.muestras(D, v, p, fut, inicio)
    s = M["sel"]
    nf = M["F"].shape[1]
    mt.liberar()
    mA, mB, ep = mt.entrenar_AB(mt._entrada(M, s["train"]), M["Y"][s["train"]], mt._entrada(M, s["val"]), M["Y"][s["val"]],
                                mt._entrada(M, s["tv"]), M["Y"][s["tv"]], p, M["X"].shape[2], nf)
    mA.save(os.path.join(destino, "lstm_rellenada_A.keras"))
    mB.save(os.path.join(destino, "lstm_rellenada_B.keras"))
    # control: reproduce las predicciones de F2c_r en la prueba
    usaB = np.asarray(M["O"] >= D["fin_val"])
    pB = pd.DataFrame(mB.predict(mt._entrada(M, usaB), verbose=0) * M["sd"] + M["mu"], index=M["O"][usaB], columns=mt.H).stack()
    pB.index.names = LLAVE
    ref_ = r_["pred"].set_index(LLAVE)["var_log"]
    dif = (pB.reindex(ref_.index) - ref_).abs().max()
    # pronóstico desde L
    iL = list(M["O"]).index(L)
    lstm_log = mB.predict(mt._entrada(M, np.arange(len(M["O"])) == iL), verbose=0)[0] * M["sd"] + M["mu"]
    m = wp.ajustar_prophet(ds, L, cfg["regimen"], wp.params_prophet(clave))
    pr = wp.predecir(m, futuras, ds.loc[L, "OPERACION_CAUSAL"] if cfg["regimen"] else None, True)
    el = r_["info"]["eleccion_val"]
    filas = []
    for k, h in enumerate(wc.HORIZONTES):
        f = futuras[k]
        w, duan, fd = el[h]["w_prophet"], el[h]["duan"], el[h]["factor_duan"]
        centro = w * pr.at[f, "yhat"] + (1 - w) * lstm_log[k]
        dlt = centro - pr.at[f, "yhat"]
        filas.append({"estacion": est, "origen": L.date(), "horizonte": h, "fecha_objetivo": f.date(),
                      "valor": float(np.exp(centro) * fd - 1 if duan else np.expm1(centro)),
                      "limite_inferior": float(np.expm1(pr.at[f, "yhat_lower"] + dlt)),
                      "limite_superior": float(np.expm1(pr.at[f, "yhat_upper"] + dlt)),
                      "w_prophet": w, "duan": duan, "prophet": float(np.expm1(pr.at[f, "yhat"])), "lstm": float(np.expm1(lstm_log[k]))})
    out = pd.DataFrame(filas)
    out.to_csv(os.path.join(destino, "pronostico_futuro.csv"), sep=";", index=False, encoding="utf-8-sig")
    print(f"{est}: último día con medición {L.date()} | control F2c_r (máx. dif. log) = {dif:.6f}")
    print(out[["fecha_objetivo", "horizonte", "valor", "limite_inferior", "limite_superior", "prophet", "lstm"]].round(2).to_string(index=False), flush=True)
    del mA, mB
    mt.liberar()
