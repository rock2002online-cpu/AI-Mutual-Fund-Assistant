import streamlit as st


def load_css():
    st.markdown(
        """
        <style>

        /* ---------- App ---------- */

        .main {
            background: #F8FAFC;
        }

        .block-container{
            max-width:1400px;
            padding-top:2rem;
            padding-bottom:2rem;
            padding-left:2rem;
            padding-right:2rem;
        }

        /* ---------- Typography ---------- */

        h1{
            color:#0F172A;
            font-weight:700;
        }

        h2{
            color:#1E293B;
            font-weight:600;
        }

        h3{
            color:#334155;
            font-weight:600;
        }

        p{
            color:#475569;
        }

        /* ---------- Cards ---------- */

        .metric-card{

            background:white;

            border:1px solid #E2E8F0;

            border-radius:16px;

            padding:20px;

            box-shadow:0 4px 12px rgba(15,23,42,.05);

            transition:all .25s ease;

            margin-bottom:10px;

        }

        .metric-card:hover{

            box-shadow:0 10px 24px rgba(15,23,42,.12);

            transform:translateY(-2px);

        }

        /* ---------- Section Container ---------- */

        .section-card{

            background:white;

            border-radius:18px;

            border:1px solid #E2E8F0;

            padding:24px;

            margin-bottom:20px;

        }

        /* ---------- Dataframe ---------- */

        .stDataFrame{

            border-radius:12px;

            overflow:hidden;

            border:1px solid #E2E8F0;

        }

        /* ---------- Metric ---------- */

        div[data-testid="metric-container"]{

            background:white;

            border:1px solid #E2E8F0;

            border-radius:16px;

            padding:18px;

            box-shadow:0 4px 12px rgba(0,0,0,.05);

        }

        /* ---------- Buttons ---------- */

        .stButton > button{

            border-radius:10px;

            font-weight:600;

            height:44px;

        }

        /* ---------- Divider ---------- */

        hr{

            margin-top:1rem;

            margin-bottom:1rem;

        }

        </style>
        """,
        unsafe_allow_html=True,
    )