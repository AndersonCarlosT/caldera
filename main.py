import streamlit as st
import pandas as pd
import io

st.title("📊 Comparador de Perfiles de Carga - Varios Archivos LP")

# Subir múltiples archivos
archivos_lp = st.file_uploader("Sube uno o más archivos .LP", type=["lp"], accept_multiple_files=True)

if archivos_lp:
    # Selector de mes y año
    meses = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
        "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
        "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
    }

    col1, col2 = st.columns(2)
    with col1:
        mes_seleccionado = st.selectbox("Selecciona el mes", list(meses.keys()))
        numero_mes = meses[mes_seleccionado]

    with col2:
        anio_seleccionado = st.selectbox("Selecciona el año", list(range(2020, 2031)), index=5)

    # Ingresar días feriados
    feriados_input = st.text_input(f"Ingrese los días feriados de {mes_seleccionado} separados por comas (ejemplo: 5,7,15):")

    if feriados_input.strip() != "":
        try:
            dias_feriados = [int(x.strip()) for x in feriados_input.split(",")]
        except:
            st.error("Formato inválido. Escriba números separados por comas.")
            dias_feriados = []
    else:
        dias_feriados = []

    # Crear dataframe base con fecha y hora
    df_final = None

    for idx, archivo in enumerate(archivos_lp):
        contenido = archivo.read().decode('utf-8')
        lineas = contenido.splitlines()

        # Buscar inicio de la tabla
        indice_inicio = None
        for i, linea in enumerate(lineas):
            if linea.strip().startswith("Fecha/Hora"):
                indice_inicio = i
                break

        if indice_inicio is None:
            st.error(f"No se encontró la cabecera 'Fecha/Hora' en {archivo.name}.")
            continue

        # Leer tabla
        tabla = "\n".join(lineas[indice_inicio:])
        df = pd.read_csv(io.StringIO(tabla), sep=";", engine='python')

        # Limpiar columnas y espacios
        df.columns = [col.strip() for col in df.columns]
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.dropna(axis=1, how='all')

        # Eliminar "+Q/kvar"
        df = df.drop(columns=[col for col in df.columns if "Q/kvar" in col], errors='ignore')

        # Convertir a datetime
        df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')

        # Filtrar por mes y año
        df_mes = df[(df['Fecha/Hora'].dt.month == numero_mes) & (df['Fecha/Hora'].dt.year == anio_seleccionado)]

        # Separar fecha y hora
        df_mes['Fecha'] = df_mes['Fecha/Hora'].dt.strftime('%d/%m/%Y')
        df_mes['Hora'] = df_mes['Fecha/Hora'].dt.strftime('%H:%M:%S')
        df_mes['Dia'] = df_mes['Fecha/Hora'].dt.day
        df_mes['Dia_semana'] = df_mes['Fecha/Hora'].dt.dayofweek  # Lunes=0, Domingo=6

        # Clasificación HP / HFP
        def clasificar(row):
            dia = row['Dia']
            dia_semana = row['Dia_semana']
            hora = pd.to_datetime(row['Hora'], format='%H:%M:%S').time()

            if dia in dias_feriados or dia_semana == 6:
                return "HFP"
            if hora >= pd.to_datetime("23:15:00", format='%H:%M:%S').time() or hora <= pd.to_datetime("18:00:00", format='%H:%M:%S').time():
                return "HFP"
            else:
                return "HP"

        df_mes['Horario'] = df_mes.apply(clasificar, axis=1)

        # Preparar dataframe para merge
        columna_p = [col for col in df_mes.columns if "+P" in col][0]
        df_merge = df_mes[['Fecha', 'Hora', 'Horario', columna_p]].copy()
        df_merge = df_merge.rename(columns={columna_p: f"+P/kW archivo {idx+1}"})

        if df_final is None:
            df_final = df_merge
        else:
            # Unimos por Fecha, Hora y Horario
            df_final = pd.merge(df_final, df_merge, on=['Fecha', 'Hora', 'Horario'], how='outer')

    if df_final is not None:
        # Ordenar columnas
        columnas_ordenadas = ['Fecha', 'Hora', 'Horario'] + [col for col in df_final.columns if col.startswith("+P/kW")]
        df_final = df_final[columnas_ordenadas]

        st.success("Datos combinados correctamente ✅")
        st.dataframe(df_final)
