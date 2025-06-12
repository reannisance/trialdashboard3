import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import BytesIO

# ---------- FUNGSI UTAMA (VERSI SUPER FIX) ----------
def process_data(df_input, tahun_pajak, jenis_pajak):
    df = df_input.copy()
    df.columns = df.columns.str.strip().str.upper()

    # --------- Normalisasi kolom wajib ---------
    alias_map = {
        'NM UNIT': ['NM UNIT', 'NAMA UNIT', 'UPPPD', 'UNIT', 'UNIT PAJAK'],
        'STATUS': ['STATUS'],
        'TMT': ['TMT'],
        'KLASIFIKASI': ['KLASIFIKASI', 'KATEGORI', 'JENIS']
    }

    def find_column(possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None

    # Cari kolom wajib utama
    kolom_nm_unit = find_column(alias_map['NM UNIT'])
    kolom_status = find_column(alias_map['STATUS'])
    kolom_tmt = find_column(alias_map['TMT'])
    kolom_klasifikasi = find_column(alias_map['KLASIFIKASI'])  # Optional

    # Validasi wajib minimum
    if not all([kolom_nm_unit, kolom_status, kolom_tmt]):
        raise ValueError("❌ Kolom wajib 'NM UNIT/UPPPD', 'STATUS', atau 'TMT' tidak ditemukan.")

    # Validasi kolom KLASIFIKASI hanya untuk jenis pajak HIBURAN
    if jenis_pajak.upper() == "JASA KESENIAN DAN HIBURAN" and not kolom_klasifikasi:
        raise ValueError("❌ Kolom 'KLASIFIKASI' wajib untuk jenis pajak HIBURAN.")

    # Rename kolom supaya konsisten
    df.rename(columns={
        kolom_nm_unit: 'NM UNIT',
        kolom_status: 'STATUS',
        kolom_tmt: 'TMT',
        **({kolom_klasifikasi: 'KLASIFIKASI'} if kolom_klasifikasi else {})
    }, inplace=True)

    df['TMT'] = pd.to_datetime(df['TMT'], errors='coerce')

    # Validasi kolom pembayaran
    payment_cols = []
    for col in df.columns:
        try:
            col_date = pd.to_datetime(col, format="%b-%y", errors="coerce")
            if pd.isna(col_date):
                col_date = pd.to_datetime(col, errors="coerce")
            if pd.notna(col_date) and col_date.year == tahun_pajak:
                if pd.to_numeric(df[col], errors='coerce').notna().sum() > 0:
                    payment_cols.append(col)
        except:
            continue

    if not payment_cols:
        raise ValueError("❌ Tidak ditemukan kolom pembayaran valid untuk tahun pajak yang dipilih.")

    df['Total Pembayaran'] = df[payment_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)

    bulan_aktif = []
    for idx, row in df.iterrows():
        tmt = row['TMT']
        if pd.isna(tmt):
            bulan_aktif.append(0)
        else:
            start = max(pd.Timestamp(year=tahun_pajak, month=1, day=1), tmt)
            end = pd.Timestamp(year=tahun_pajak, month=12, day=31)
            active_months = max(0, (end.year - start.year) * 12 + (end.month - start.month) + 1)
            bulan_aktif.append(active_months)
    df['Bulan Aktif'] = bulan_aktif
    df['Jumlah Pembayaran'] = df[payment_cols].apply(lambda x: pd.to_numeric(x, errors='coerce').gt(0).sum(), axis=1)

    def hitung_kepatuhan(row):
        payments = pd.to_numeric(row[payment_cols], errors='coerce').fillna(0)
        aktif = row['Bulan Aktif']
        bayar = payments.gt(0).astype(int).values
        gap = 0
        max_gap = 0
        for v in bayar:
            if v == 0:
                gap += 1
                max_gap = max(max_gap, gap)
            else:
                gap = 0
        return 100.0 if max_gap < 3 else round((row['Jumlah Pembayaran'] / aktif) * 100, 2) if aktif > 0 else 0.0

    df['Kepatuhan (%)'] = df.apply(hitung_kepatuhan, axis=1)
    df['Total Pembayaran'] = df['Total Pembayaran'].map(lambda x: f"{x:,.2f}")
    df['Kepatuhan (%)'] = df['Kepatuhan (%)'].map(lambda x: f"{x:.2f}")

    return df, payment_cols
