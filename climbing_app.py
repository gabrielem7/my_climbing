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
    df_lines.loc[valid_dates, 'year'] = df_lines.loc[valid_dates, 'date'].dt.year.astype(int)#.astype(str)
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
    'on sight / flash': '#17becf'
}
# --- ORDINE STATUS ---
list_status_order = [
    'on sight',
    'flash',
    'on sight / flash',
    'redpoint',
    'clean',
    '1p',
    '2p',
    '3p',
    '3p+',
    'not finished',
    'projecting'
]
# Dizionario numerico per ordinare i dataframe
status_order_map = {s: i for i, s in enumerate(list_status_order)}

########################################################################################################################

# --- SIDEBAR GENERALE ---
st.sidebar.header("Impostazioni Globali")

# 1. Aggregazione Temporale (Switch per i grafici)
time_agg_map = {"Mese": "month", "Trimestre": "quarter", "Semestre": "semester", "Anno": "year"}
selected_time_agg = st.sidebar.selectbox("Aggregazione Temporale", list(time_agg_map.keys()))
time_col = time_agg_map[selected_time_agg] 

# 2. Accorpamento On Sight e Flash
merge_flash_os = st.sidebar.checkbox("Accorpa Flash e On Sight")

if merge_flash_os:
    df_lines['status'] = df_lines['status'].replace({'flash': 'on sight / flash', 'on sight': 'on sight / flash'})

########################################################################################################################

# --- SEZIONE 1: GENERALE ---
st.markdown("### 📊 Overview Volume")

min_year_ov = int(df_lines['year'].min())
max_year_ov = int(df_lines['year'].max())
years_ov = st.slider("Filtra Anni Overview", min_year_ov, max_year_ov, (min_year_ov, max_year_ov))

# Applica il filtro anni solo per l'overview
df_lines_ov = df_lines[df_lines['year'].between(years_ov[0], years_ov[1])].copy()

# 1. Estrai le colonne chiave, aggiungendo 'description' (Luogo)
df_daily = df_lines_ov[['session_id', 'date', time_col, 'climbing_type', 'description']].dropna(subset=['climbing_type']).drop_duplicates()

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

# --- METRICHE CLIMBING AVANZATE ---
giorni_totali = df_daily_clean['date'].nunique()
time_col_attivi = df_daily_clean[time_col].nunique()
media_time_col = round(giorni_totali / time_col_attivi, 1) if time_col_attivi > 0 else 0

completed_df = df_lines_ov['status'].isin(['on sight', 'flash', 'redpoint', 'on sight / flash'])
completed_df_multipitch = df_lines_ov['status'].isin(['on sight', 'flash', 'redpoint', 'on sight / flash', 'clean'])

# Render in colonne
met_1, met_2, met_3, met_4, met_5= st.columns(5)
met_1.metric("🗓️ Giorni di Arrampicata", giorni_totali)
met_2.metric("🔄 Media Sessioni/Periodo selezionato nel filtro", f"{media_time_col}")
met_3.metric("🪢 Tiri Corda", len(df_lines_ov[completed_df & df_lines_ov['climbing_type'].isin(['rock climbing', 'indoor climbing', 'trad climbing'])])) 
met_4.metric("🧗‍♂️ Blocchi Boulder", len(df_lines_ov[completed_df & df_lines_ov['climbing_type'].isin(['indoor boulder', 'rock boulder'])])) 
met_5.metric("🏔️ Vie Multipitch", len(df_lines_ov[completed_df_multipitch & (df_lines_ov['climbing_type'] == 'multipitch')]))
st.markdown("<br>", unsafe_allow_html=True)

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
    title_text="Numero di Sessioni Periodo Selezionato",
    title_font=dict(size=14),
    xaxis_title="Periodo Selezionato", 
    yaxis_title="Sessioni", 
    legend_title="", # Tolgo il titolo "climbing_type" per risparmiare spazio
    margin=dict(l=0, r=0, t=40, b=0),
    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5)
)
# Calcola i totali per mese
df_vol_totals = df_vol.groupby(time_col)['sessions'].sum().reset_index()

# Aggiunge i totali in cima alle colonne
fig_vol.add_trace(go.Scatter(
    x=df_vol_totals[time_col], 
    y=df_vol_totals['sessions'],
    text=df_vol_totals['sessions'], 
    mode='text',
    textposition='top center',
    showlegend=False,
    hoverinfo='skip'
))

st.plotly_chart(fig_vol,  width='stretch')

########################################################################################################################

# --- SEZIONE 2: CORDA ---
st.header("🪢 Arrampicata su Corda")
df_rope = df_lines[df_lines['climbing_type'].isin(['rock climbing', 'indoor climbing','trad climbing'])].copy()
df_rope['grade_numeric'] = df_rope['grade'].map(grade_order_rope)

with st.expander("🔍 Filtri Corda"):
    col1, col2 = st.columns(2)
    
    with col1:
        min_y_r, max_y_r = int(df_rope['year'].min()), int(df_rope['year'].max())
        r_years = st.slider("Anni (Corda)", min_y_r, max_y_r, (min_y_r, max_y_r))
        
        available_grades_rope = sorted(df_rope['grade'].dropna().unique())
        r_grades = st.multiselect("Gradi", available_grades_rope, help="Lascia vuoto per tutti")
        
        available_types = df_rope['climbing_type'].dropna().unique()
        r_types = st.multiselect("Ambiente", available_types, default=available_types)
        
    with col2:
        available_places = sorted(df_rope['description'].dropna().unique())
        r_places = st.multiselect("Luogo", available_places)
        
        present_status = df_rope['status'].dropna().unique()
        available_status = [s for s in list_status_order if s in present_status]
        safe_defaults_status = [s for s in ['on sight', 'flash', 'redpoint', 'on sight / flash'] if s in available_status]
        r_status = st.multiselect("Status", available_status, default=safe_defaults_status)
        
        available_styles = df_rope['climbing_style'].dropna().unique()
        r_style = st.multiselect("Stile", available_styles, default=["lead"] if "lead" in available_styles else None)

    all_holds = df_rope['holds_type'].dropna().astype(str).str.split(',').explode().str.strip()
    available_holds = sorted([h for h in all_holds.unique() if h])
    r_holds = st.multiselect("Prese", available_holds)

def check_holds(row_val, selected_holds):
    if pd.isna(row_val): return False
    row_holds = [x.strip() for x in str(row_val).split(',')]
    return any(h in row_holds for h in selected_holds)

# Filtraggio sequenziale e pulito
df_rope_filt = df_rope[df_rope['year'].between(r_years[0], r_years[1])].copy()

if len(r_grades) > 0: df_rope_filt = df_rope_filt[df_rope_filt['grade'].isin(r_grades)]
if len(r_types) > 0: df_rope_filt = df_rope_filt[df_rope_filt['climbing_type'].isin(r_types)]
if len(r_places) > 0: df_rope_filt = df_rope_filt[df_rope_filt['description'].isin(r_places)]
if len(r_status) > 0: df_rope_filt = df_rope_filt[df_rope_filt['status'].isin(r_status)]
if len(r_style) > 0: df_rope_filt = df_rope_filt[df_rope_filt['climbing_style'].isin(r_style)]
if len(r_holds) > 0: df_rope_filt = df_rope_filt[df_rope_filt['holds_type'].apply(lambda x: check_holds(x, r_holds))]

if not df_rope_filt.empty:
   
    met_c_1, met_c_2, met_c_3, met_c_4, met_c_5= st.columns(5)
    met_c_1.metric("🧗‍♂️ Tiri Corda", len(df_rope_filt[df_rope_filt['climbing_type'].isin(['rock climbing', 'indoor climbing', 'trad climbing'])]))
    met_c_2.metric("🔥 Max Grado Chiuso (Corda)", df_rope_filt[df_rope_filt['status'].isin(['redpoint', 'flash', 'on sight', 'on sight / flash'])]['grade'].max())
    met_c_3.metric("👁️ Max a Vista/Flash (Corda)", df_rope_filt[df_rope_filt['status'].isin(['on sight', 'flash', 'on sight / flash'])]['grade'].max())
     
    st.markdown("<br>", unsafe_allow_html=True)

    df_pyramid = df_rope_filt.groupby(['grade', 'status']).size().reset_index(name='count')
    df_pyramid['numeric'] = df_pyramid['grade'].map(grade_order_rope)
    df_pyramid = df_pyramid.sort_values('numeric', ascending=True)
    
    # 1. CREIAMO LA COLONNA PRIMA DEL GRAFICO
    df_pyramid['text_label'] = df_pyramid['count'].apply(lambda x: str(x) if x > 2 else "")
    
    # 2. CREIAMO IL GRAFICO PASSANDO LA NUOVA COLONNA
    fig_pyr = px.bar(df_pyramid, x='count', y='grade', color='status', orientation='h', 
                     title="Piramide dei Gradi Globale", text='text_label',
                     color_discrete_map=color_map_status,
                     category_orders={'status': list_status_order})
                     
    # 3. AGGIUNGIAMO I TOTALI
    df_pyr_totals = df_pyramid.groupby('grade')['count'].sum().reset_index()
    fig_pyr.add_trace(go.Scatter(
        x=df_pyr_totals['count'], 
        y=df_pyr_totals['grade'],
        text=df_pyr_totals['count'], 
        mode='text',
        textposition='middle right',
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # 4. LAYOUT
    fig_pyr.update_layout(
        barmode='stack', 
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5)
    )
    
    # 5. TESTO INTERNO (DRITTO E DENTRO LA BARRA)
    fig_pyr.update_traces(textangle=0, textposition='inside', selector=dict(type="bar"))

    st.plotly_chart(fig_pyr, width='stretch')

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
                       title="Volume Gradi nel Tempo",
                       category_orders={'grade_grouped': grouped_order},
                       labels={'grade_grouped': 'Grado'})
    # Calcola i totali per mese
    df_pyr_m_totals = df_pyr_month.groupby(time_col)['count'].sum().reset_index()

    # Aggiunge i totali in cima alle colonne
    fig_pyr_m.add_trace(go.Scatter(
        x=df_pyr_m_totals[time_col], 
        y=df_pyr_m_totals['count'],
        text=df_pyr_m_totals['count'], 
        mode='text',
        textposition='top center',
        showlegend=False,
        hoverinfo='skip'
    ))
    fig_pyr_m.update_layout(margin=dict(l=0, r=0, t=40, b=0),legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    st.plotly_chart(fig_pyr_m,  width='stretch')

    df_max = df_rope_filt.groupby([time_col])['grade_numeric'].max().reset_index()
    reverse_rope = {v: k for k, v in grade_order_rope.items()}
    df_max['max_grade'] = df_max['grade_numeric'].map(reverse_rope)
    fig_max = px.line(df_max, x=time_col, y='max_grade', markers=True, title="Grado Massimo nel Tempo",
                      category_orders={'max_grade': list_grades_rope})
    fig_max.update_layout(margin=dict(l=0, r=0, t=40, b=0),legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    fig_max.update_yaxes(categoryorder='array', categoryarray=list_grades_rope)
    st.plotly_chart(fig_max,  width='stretch')

    df_max_stat = df_rope_filt.groupby([time_col, 'status'])['grade_numeric'].max().reset_index()
    df_max_stat['max_grade'] = df_max_stat['grade_numeric'].map(reverse_rope)
    fig_max_stat = px.line(df_max_stat, x=time_col, y='max_grade', color='status', markers=True, 
                           title="Max Grado nel Tempo per Status",
                           color_discrete_map=color_map_status,
                           category_orders={'max_grade': list_grades_rope, 'status': list_status_order})
    fig_max_stat.update_layout(margin=dict(l=0, r=0, t=40, b=0),legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    fig_max_stat.update_yaxes(categoryorder='array', categoryarray=list_grades_rope)
    st.plotly_chart(fig_max_stat,  width='stretch')
    
    # 2.5 Tabella Migliori Tiri
    st.markdown("#### 🏆 I Migliori Tiri Completati")
    
    
    
    if not df_rope_filt.empty:
        # Ordiniamo per grado numerico decrescente e per data più recente a parità di grado
        df_best = df_rope_filt.sort_values(by=['grade_numeric', 'date'], ascending=[False, False])
        
        # Prendiamo i top 20 e le colonne più rilevanti
        df_best_view = df_best[['date', 'description', 'name', 'grade', 'status', 'climbing_style','holds_type', 'comment']].head(20).copy()
        df_best_view['date'] = df_best_view['date'].dt.strftime('%d/%m/%Y')
        
        # Rinominiamo per estetica
        df_best_view = df_best_view.rename(columns={
            'date': 'Data', 'description': 'Luogo', 'name': 'Via', 
            'grade': 'Grado', 'status': 'Status', 'climbing_style': 'Stile',
            'holds_type': 'Prese', 'comment': 'Note'
        })
        
        st.dataframe(df_best_view,  width='stretch', hide_index=True)
    else:
        st.info("Nessuna salita completata trovata con i filtri attuali.")
else:
    st.info("Nessun dato per i filtri selezionati.")

########################################################################################################################

# --- SEZIONE 3: BOULDER ---
st.markdown("---")
st.header("🧗‍♂️ Boulder")

df_boulder = df_lines[df_lines['climbing_type'].isin(['indoor boulder', 'rock boulder'])].copy()
df_boulder = df_boulder[df_boulder['grade'].isin(list_grades_boulder)]
df_boulder['grade_numeric'] = df_boulder['grade'].map(grade_order_boulder)

with st.expander("🔍 Filtri Boulder"):
    col1, col2 = st.columns(2)
    
    with col1:
        min_y_b, max_y_b = int(df_boulder['year'].min()), int(df_boulder['year'].max())
        b_years = st.slider("Anni (Boulder)", min_y_b, max_y_b, (min_y_b, max_y_b))
        
        available_grades_boulder = sorted(df_boulder['grade'].dropna().unique())
        b_grades = st.multiselect("Gradi Boulder", available_grades_boulder)
        
        available_b_types = df_boulder['climbing_type'].dropna().unique()
        b_types = st.multiselect("Ambiente Boulder", available_b_types, default=available_b_types)
        
    with col2:
        available_b_places = sorted(df_boulder['description'].dropna().unique())
        b_places = st.multiselect("Luogo Boulder", available_b_places)
        
        present_b_status = df_boulder['status'].dropna().unique()
        available_b_status = [s for s in list_status_order if s in present_b_status]        
        safe_defaults_b_status = [s for s in ['on sight', 'flash', 'redpoint', 'on sight / flash'] if s in available_b_status]
        b_status = st.multiselect("Status Boulder", available_b_status, default=safe_defaults_b_status)
        
        all_b_holds = df_boulder['holds_type'].dropna().astype(str).str.split(',').explode().str.strip()
        available_b_holds = sorted([h for h in all_b_holds.unique() if h])
        b_holds = st.multiselect("Prese Boulder", available_b_holds)

# Filtraggio sequenziale e pulito
df_boulder_filt = df_boulder[df_boulder['year'].between(b_years[0], b_years[1])].copy()

if len(b_grades) > 0: df_boulder_filt = df_boulder_filt[df_boulder_filt['grade'].isin(b_grades)]
if len(b_types) > 0: df_boulder_filt = df_boulder_filt[df_boulder_filt['climbing_type'].isin(b_types)]
if len(b_places) > 0: df_boulder_filt = df_boulder_filt[df_boulder_filt['description'].isin(b_places)]
if len(b_status) > 0: df_boulder_filt = df_boulder_filt[df_boulder_filt['status'].isin(b_status)]
if len(b_holds) > 0: df_boulder_filt = df_boulder_filt[df_boulder_filt['holds_type'].apply(lambda x: check_holds(x, b_holds))]

if not df_boulder_filt.empty:
    completed_boulder = df_lines['status'].isin(['on sight', 'flash', 'redpoint', 'on sight / flash'])
    met_b_1, met_b_2, met_b_3 = st.columns(3)
    met_b_1.metric("🧗‍♂️ Blocchi Boulder", len(df_lines[completed_boulder & df_lines['climbing_type'].isin(['indoor boulder', 'rock boulder'])]))
    met_b_2.metric("🧱 Blocchi Boulder Indoor", len(df_lines[completed_boulder & df_lines['climbing_type'].isin(['indoor boulder'])]))
    met_b_3.metric("🏔️ Blocchi Boulder Outdoor", len(df_lines[completed_boulder & df_lines['climbing_type'].isin(['rock boulder'])]))
    st.markdown("<br>", unsafe_allow_html=True)
    # --- PIRAMIDE BLOCCHI NEL TEMPO ---
    df_bp_month = df_boulder_filt.groupby([time_col, 'grade']).size().reset_index(name='count')
    fig_bp_m = px.bar(df_bp_month, x=time_col, y='count', color='grade', title="Volume Blocchi nel Tempo",
                      color_discrete_map=color_map_boulder, 
                      category_orders={'grade': list_grades_boulder})
                      
    fig_bp_m.update_layout(margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    # Calcola i totali per mese
    df_bp_totals = df_bp_month.groupby(time_col)['count'].sum().reset_index()

    # Aggiunge i totali in cima alle colonne
    fig_bp_m.add_trace(go.Scatter(
        x=df_bp_totals[time_col], 
        y=df_bp_totals['count'],
        text=df_bp_totals['count'], 
        mode='text',
        textposition='top center',
        showlegend=False,
        hoverinfo='skip'
    ))
    st.plotly_chart(fig_bp_m,  width='stretch')

    # --- GRAFICO LINEE GRADO MASSIMO ---
    df_bm_stat = df_boulder_filt.groupby([time_col, 'status'])['grade_numeric'].max().reset_index()
    reverse_boulder = {v: k for k, v in grade_order_boulder.items()}
    df_bm_stat['max_grade'] = df_bm_stat['grade_numeric'].map(reverse_boulder)
    
    fig_bm_stat = px.line(df_bm_stat, x=time_col, y='max_grade', color='status', markers=True, 
                          title="Max Colore per Status",
                          color_discrete_map=color_map_status,
                          category_orders={'status': list_status_order})
                          
    fig_bm_stat.update_layout(margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
    fig_bm_stat.update_yaxes(categoryorder='array', categoryarray=list_grades_boulder) 

    st.plotly_chart(fig_bm_stat,  width='stretch')  
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
    st.dataframe(df_multi_view[['Data', 'Via', 'Grado', 'Socio', 'Note', 'Completata']],  width='stretch', hide_index=True)
else:
    st.info("Nessuna via lunga registrata finora.")