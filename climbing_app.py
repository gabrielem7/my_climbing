import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Climbing Dashboard", layout="wide", page_icon="🧗‍♂️")
st.markdown("## 🧗‍♂️ My Climbing Dashboard")

# --- CARICAMENTO E PULIZIA DATI ---
SHEET_ID = "1aeCcRAt7baHVt3P75YTq_rSxSKOzwbjuCLpAcgIyc3Q"
URL_LINES = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=831695350"
URL_SESSIONS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=1617924867"

@st.cache_data(ttl=600)
def load_and_clean_data():
    df_sessions = pd.read_csv(URL_SESSIONS)
    df_lines = pd.read_csv(URL_LINES)
    
    # 1. Date e Mesi
    df_sessions['date'] = pd.to_datetime(df_sessions['date'], errors='coerce')
    df_lines['date'] = pd.to_datetime(df_lines['date'], errors='coerce')
    df_sessions['month'] = df_sessions['date'].dt.to_period('M').astype(str)
    df_lines['month'] = df_lines['date'].dt.to_period('M').astype(str)
    # Generazione aggregazioni temporali (Mese, Trimestre, Semestre, Anno)
    valid_dates = df_lines['date'].notna()
    df_lines.loc[valid_dates, 'year'] = df_lines.loc[valid_dates, 'date'].dt.year.astype(int).astype(str)
    df_lines.loc[valid_dates, 'quarter'] = df_lines.loc[valid_dates, 'date'].dt.to_period('Q').astype(str)
    df_lines.loc[valid_dates, 'semester'] = df_lines.loc[valid_dates, 'date'].dt.year.astype(int).astype(str) + "-H" + ((df_lines.loc[valid_dates, 'date'].dt.month - 1) // 6 + 1).astype(str)

    # 2. Pulizia Stringhe (Lower case e strip spazi) per evitare errori di case-sensitivity
    string_cols = ['climbing_type', 'grade', 'status', 'climbing_style', 'holds_type']
    for col in string_cols:
        if col in df_lines.columns:
            df_lines[col] = df_lines[col].astype(str).str.lower().str.strip()
    
    # 3. Scala Corda
    list_grades_rope = [f"{n}{l}" for n in range(3, 9) for l in ["a", "a+", "b", "b+", "c", "c+"]]
    grade_order_rope = {grade: i for i, grade in enumerate(list_grades_rope)}
    
    # 4. Scala Boulder
    list_grades_boulder = ['blu', 'verde', 'gialla']
    grade_order_boulder = {grade: i for i, grade in enumerate(list_grades_boulder)}
    
    return df_sessions, df_lines, list_grades_rope, grade_order_rope, list_grades_boulder, grade_order_boulder

# Caricamento
df_sessions, df_lines, list_grades_rope, grade_order_rope, list_grades_boulder, grade_order_boulder = load_and_clean_data()

# --- MAPPE COLORI ---
color_map_boulder = {'blu': '#1f77b4', 'verde': '#2ca02c', 'gialla': '#ffd700'}
color_map_status = {
    'on sight': '#1f77b4', 
    'flash': '#2ca02c',    
    'redpoint': '#d62728', 
    'red point': '#d62728',
    'on sight / flash': '#17becf' # Un colore ciano brillante per l'accorpamento
}

# --- SIDEBAR GENERALE ---
st.sidebar.header("Filtri Globali")

# 1. Filtro Anno (Vuoto = Tutti)
available_years = sorted(df_lines['year'].dropna().unique(), reverse=True)
selected_years = st.sidebar.multiselect("Anno", available_years, default=[], help="Lascia vuoto per selezionare tutti")
years_to_filter = selected_years if selected_years else available_years

# 2. Filtro Grado (Vuoto = Tutti)
# Ordiniamo i gradi disponibili in ordine alfabetico/numerico
available_grades = sorted(df_lines['grade'].dropna().unique())
selected_grades = st.sidebar.multiselect("Grado", available_grades, default=[], help="Lascia vuoto per selezionare tutti")
grades_to_filter = selected_grades if selected_grades else available_grades

# 3. Aggregazione Temporale (Switch per i grafici)
time_agg_map = {"Mese": "month", "Trimestre": "quarter", "Semestre": "semester", "Anno": "year"}
selected_time_agg = st.sidebar.selectbox("Aggregazione Temporale", list(time_agg_map.keys()))
time_col = time_agg_map[selected_time_agg] 

# 4. Accorpamento On Sight e Flash
merge_flash_os = st.sidebar.checkbox("Accorpa Flash e On Sight")

# APPLICAZIONE FILTRI GLOBALI
df_lines = df_lines[
    df_lines['year'].isin(years_to_filter) & 
    df_lines['grade'].isin(grades_to_filter)
].copy()

if merge_flash_os:
    df_lines['status'] = df_lines['status'].replace({'flash': 'on sight / flash', 'on sight': 'on sight / flash'})



if merge_flash_os:
    df_lines['status'] = df_lines['status'].replace({'flash': 'on sight / flash', 'on sight': 'on sight / flash'})

# --- SEZIONE 1: GENERALE ---
st.markdown("### 📊 Overview Volume")

# 1. Estrai le colonne chiave, aggiungendo 'description' (Luogo)
df_daily = df_lines[['session_id', 'date', time_col, 'climbing_type', 'description']].dropna(subset=['climbing_type']).drop_duplicates()

# 2. Isoliamo le combinazioni esatte [Data + Luogo] dominanti
idx_indoor_rope = df_daily[df_daily['climbing_type'] == 'indoor climbing'].set_index(['date', 'description']).index
idx_rock_rope = df_daily[df_daily['climbing_type'] == 'rock climbing'].set_index(['date', 'description']).index

# 3. Creiamo lo stesso indice per tutte le righe attuali per poterle confrontare
current_idx = df_daily.set_index(['date', 'description']).index

# 4. Regole di esclusione: scarta il boulder/trad SOLO se Data E Luogo coincidono con la corda
drop_indoor_boulder = (df_daily['climbing_type'] == 'indoor boulder') & current_idx.isin(idx_indoor_rope)
drop_trad = (df_daily['climbing_type'] == 'trad climbing') & current_idx.isin(idx_rock_rope)

# 5. Applica le regole e tieni solo le sessioni valide
df_daily_clean = df_daily[~(drop_indoor_boulder | drop_trad)]

# 6. Conta le sessioni
df_vol = df_daily_clean.groupby([time_col, 'climbing_type'])['session_id'].nunique().reset_index(name='sessions')
df_vol = df_vol.sort_values(time_col)

# 1. Definisci l'ordine dal basso verso l'alto
type_order = [
    'indoor boulder', 
    'indoor climbing', 
    'rock boulder', 
    'rock climbing', 
    'trad climbing', 
    'multipitch'
]

# 2. Definisci la palette di colori fissa
color_map_types = {
    'indoor boulder': '#ffb6c1',  # Rosa
    'indoor climbing': '#ff3333', # Rosso
    'rock boulder': '#7bc8f6',    # Azzurro
    'rock climbing': '#0062cc',   # Blu scuro
    'trad climbing': '#86f2a2',   # Verdino
    'multipitch': '#2eb09a'       # Verdone
}

# 3. Applica ordine e colori al grafico
fig_vol = px.bar(df_vol, x=time_col, y='sessions', color='climbing_type', 
                 barmode='stack',
                 category_orders={'climbing_type': type_order},
                 color_discrete_map=color_map_types)

fig_vol.update_layout(
    title_text="Numero di Sessioni Mensili",
    title_font=dict(size=14),
    xaxis_title="Mese", 
    yaxis_title="Sessioni", 
    legend_title="", # Tolgo il titolo "climbing_type" per risparmiare spazio
    margin=dict(l=0, r=0, t=40, b=0),
    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5)
)

st.plotly_chart(fig_vol, use_container_width=True)


# --- SEZIONE 2: CORDA ---
st.header("🪢 Arrampicata su Corda")
df_rope = df_lines[df_lines['climbing_type'].isin(['rock climbing', 'indoor climbing','trad climbing'])].copy()
df_rope['grade_numeric'] = df_rope['grade'].map(grade_order_rope)

with st.expander("🔍 Filtri Corda"):
    available_types = df_rope['climbing_type'].dropna().unique()
    r_types = st.multiselect("Ambiente", available_types, default=available_types)
    
    available_status = df_rope['status'].dropna().unique()
    safe_defaults_status = [s for s in ['on sight', 'flash', 'redpoint', 'on sight / flash'] if s in available_status]
    r_status = st.multiselect("Status", available_status, default=safe_defaults_status)
    
    available_styles = df_rope['climbing_style'].dropna().unique()
    r_style = st.multiselect("Stile", available_styles, default="lead") 
    
    available_holds = df_rope['holds_type'].dropna().unique()
    r_holds = st.multiselect("Prese", available_holds)

df_rope_filt = df_rope[
    (df_rope['climbing_type'].isin(r_types)) &
    (df_rope['status'].isin(r_status)) &
    (df_rope['climbing_style'].isin(r_style) if len(r_style) > 0 else True) &
    (df_rope['holds_type'].isin(r_holds) if len(r_holds) > 0 else True)
]

if not df_rope_filt.empty:
    df_pyramid = df_rope_filt.groupby(['grade', 'status']).size().reset_index(name='count')
    df_pyramid['numeric'] = df_pyramid['grade'].map(grade_order_rope)
    df_pyramid = df_pyramid.sort_values('numeric', ascending=True)
    
    fig_pyr = px.bar(df_pyramid, x='count', y='grade', color='status', orientation='h', 
                     title="Piramide dei Gradi Globale", text='count',
                     color_discrete_map=color_map_status)
                     
    fig_pyr.update_layout(barmode='stack', margin=dict(l=0, r=0, t=40, b=0),legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    st.plotly_chart(fig_pyr, use_container_width=True)

    def group_grade(g):
        g = str(g)
        if g.startswith(('3', '4', '5')):
            return g[0] # Ritorna solo '3', '4' o '5'
        elif len(g) >= 2:
            return g[:2] # Ritorna '6a', '6b', ecc., tagliando via il '+'
        return g

    # Creiamo un dataframe temporaneo assegnando la nuova colonna per non intaccare gli altri grafici
    df_temp_pyr = df_rope_filt.assign(grade_grouped=df_rope_filt['grade'].apply(group_grade))
    
    # Raggruppiamo per time_col e per il nuovo grado raggruppato
    df_pyr_month = df_temp_pyr.groupby([time_col, 'grade_grouped']).size().reset_index(name='count')
    
    # Creiamo l'ordine corretto per le categorie raggruppate
    grouped_order = ['3', '4', '5', '6a', '6b', '6c', '7a', '7b', '7c', '8a', '8b', '8c']
    
    # Creiamo il grafico
    fig_pyr_m = px.bar(df_pyr_month, x=time_col, y='count', color='grade_grouped', 
                       title="Volume Gradi per Mese",
                       category_orders={'grade_grouped': grouped_order},
                       labels={'grade_grouped': 'Grado'})
    fig_pyr_m.update_layout(margin=dict(l=0, r=0, t=40, b=0),legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    st.plotly_chart(fig_pyr_m, use_container_width=True)

    df_max = df_rope_filt.groupby([time_col])['grade_numeric'].max().reset_index()
    reverse_rope = {v: k for k, v in grade_order_rope.items()}
    df_max['max_grade'] = df_max['grade_numeric'].map(reverse_rope)
    fig_max = px.line(df_max, x=time_col, y='max_grade', markers=True, title="Grado Massimo Mensile Assoluto",
                      category_orders={'max_grade': list_grades_rope})
    fig_max.update_layout(margin=dict(l=0, r=0, t=40, b=0),legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    fig_max.update_yaxes(categoryorder='array', categoryarray=list_grades_rope)
    st.plotly_chart(fig_max, use_container_width=True)

    df_max_stat = df_rope_filt.groupby([time_col, 'status'])['grade_numeric'].max().reset_index()
    df_max_stat['max_grade'] = df_max_stat['grade_numeric'].map(reverse_rope)
    fig_max_stat = px.line(df_max_stat, x=time_col, y='max_grade', color='status', markers=True, 
                           title="Max Grado Mensile per Status",
                           color_discrete_map=color_map_status,
                           category_orders={'max_grade': list_grades_rope})
    fig_max_stat.update_layout(margin=dict(l=0, r=0, t=40, b=0),legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    fig_max_stat.update_yaxes(categoryorder='array', categoryarray=list_grades_rope)
    st.plotly_chart(fig_max_stat, use_container_width=True)
    
    # 2.5 Tabella Migliori Tiri
    st.markdown("#### 🏆 I Migliori Tiri Completati")
    
    # Filtriamo solo le salite valide (ignorando i tentativi o le non chiuse)
    valid_statuses = ['on sight', 'flash', 'redpoint', 'clean', 'on sight / flash']
    df_best = df_rope_filt[df_rope_filt['status'].isin(valid_statuses)].copy()
    
    if not df_best.empty:
        # Ordiniamo per grado numerico decrescente e per data più recente a parità di grado
        df_best = df_best.sort_values(by=['grade_numeric', 'date'], ascending=[False, False])
        
        # Prendiamo i top 15 e le colonne più rilevanti
        df_best_view = df_best[['date', 'description', 'name', 'grade', 'status', 'climbing_style', 'comment']].head(15).copy()
        df_best_view['date'] = df_best_view['date'].dt.strftime('%d/%m/%Y')
        
        # Rinominiamo per estetica
        df_best_view = df_best_view.rename(columns={
            'date': 'Data', 'description': 'Luogo', 'name': 'Via', 
            'grade': 'Grado', 'status': 'Status', 'climbing_style': 'Stile', 'comment': 'Note'
        })
        
        st.dataframe(df_best_view, use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna salita completata trovata con i filtri attuali.")
else:
    st.info("Nessun dato per i filtri selezionati.")


# --- SEZIONE 3: BOULDER ---
st.markdown("---")
st.header("🧗‍♂️ Boulder")

df_boulder = df_lines[df_lines['climbing_type'].isin(['indoor boulder', 'rock boulder'])].copy()
df_boulder = df_boulder[df_boulder['grade'].isin(list_grades_boulder)]
df_boulder['grade_numeric'] = df_boulder['grade'].map(grade_order_boulder)

with st.expander("🔍 Filtri Boulder"):
    available_b_types = df_boulder['climbing_type'].dropna().unique()
    b_types = st.multiselect("Ambiente Boulder", available_b_types, default=available_b_types)
    
    available_b_status = df_boulder['status'].dropna().unique()
    safe_defaults_b_status = [s for s in ['on sight', 'flash', 'redpoint', 'on sight / flash'] if s in available_b_status]
    b_status = st.multiselect("Status Boulder", available_b_status, default=safe_defaults_b_status)

df_boulder_filt = df_boulder[
    (df_boulder['climbing_type'].isin(b_types)) &
    (df_boulder['status'].isin(b_status))
]

if not df_boulder_filt.empty:
    # --- PIRAMIDE BLOCCHI NEL TEMPO ---
    df_bp_month = df_boulder_filt.groupby([time_col, 'grade']).size().reset_index(name='count')
    fig_bp_m = px.bar(df_bp_month, x=time_col, y='count', color='grade', title="Volume Blocchi nel Tempo",
                      color_discrete_map=color_map_boulder, 
                      category_orders={'grade': list_grades_boulder})
                      
    fig_bp_m.update_layout(margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    st.plotly_chart(fig_bp_m, use_container_width=True)

    # --- GRAFICO LINEE GRADO MASSIMO ---
    df_bm_stat = df_boulder_filt.groupby([time_col, 'status'])['grade_numeric'].max().reset_index()
    reverse_boulder = {v: k for k, v in grade_order_boulder.items()}
    df_bm_stat['max_grade'] = df_bm_stat['grade_numeric'].map(reverse_boulder)
    
    fig_bm_stat = px.line(df_bm_stat, x=time_col, y='max_grade', color='status', markers=True, 
                          title="Max Colore per Status",
                          color_discrete_map=color_map_status)
                          
    fig_bm_stat.update_layout(margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    fig_bm_stat.update_yaxes(categoryorder='array', categoryarray=list_grades_boulder) 
    
    st.plotly_chart(fig_bm_stat, use_container_width=True)  
else:
    st.info("Nessun dato per i filtri selezionati.")

# --- SEZIONE 4: MULTIPITCH ---
st.markdown("---")
st.header("⛰️ Multipitch")

df_multi = df_lines[df_lines['climbing_type'] == 'multipitch'].copy()

if not df_multi.empty:
    # Flag Trad
    df_multi['is_trad'] = df_multi['comment'].astype(str).str.contains(r'trad|integrare', case=False, na=False)
    
    # Nuovo Flag Completata (True se diverso da 'not finished')
    df_multi['is_finished'] = df_multi['status'].astype(str).str.lower() != 'not finished'
    
    col_a, col_b = st.columns(2)
    col_a.metric("Totale Vie Lunghe completate", df_multi['is_finished'].sum())
    col_b.metric("Di cui Trad/Integrare", df_multi[df_multi['is_finished']]['is_trad'].sum())
    
    # IMPORTANTE: Aggiunto 'name' e 'is_finished' all'estrazione per evitare errori
    df_multi_view = df_multi[['date', 'description', 'name', 'grade', 'comment', 'is_trad', 'is_finished']].sort_values('date', ascending=False)
    df_multi_view['date'] = df_multi_view['date'].dt.strftime('%d/%m/%Y')
    
    def format_description(row):
        return f"🛡️ {row['description']}" if row['is_trad'] else row['description']
        
    df_multi_view['description'] = df_multi_view.apply(format_description, axis=1)
    
    # Rinomina per la UI
    df_multi_view = df_multi_view.rename(columns={
        'date': 'Data', 
        'description': 'Via', 
        'grade': 'Grado', 
        'comment': 'Note', 
        'name': 'Socio',
        'is_finished': 'Completata'
    })
    
    # Visualizza la tabella includendo Socio e Completata
    st.dataframe(df_multi_view[['Data', 'Via', 'Grado', 'Socio', 'Note', 'Completata']], use_container_width=True, hide_index=True)
else:
    st.info("Nessuna via lunga registrata finora.")