@echo off
chcp 65001 >nul
title ACTUALIZADOR DATOS TRADING - MM LADRÓN DEL DOJI

echo.
echo ========================================
echo   ACTUALIZADOR DATOS TRADING
echo   MM LADRÓN DEL DOJI - GitHub Pages
echo ========================================
echo.

echo 🕐 Fecha y hora: %date% %time%
echo.

echo 🔄 Conectando con MT5...
python update_trading_data.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ Error al ejecutar el script Python
    echo 📢 Verifica que Python esté instalado y las dependencias también
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ Proceso completado exitosamente!
echo.

echo 📊 RESUMEN:
echo    - Archivo generado: web_data.json en el Escritorio
echo    - Listo para subir a la web
echo.

echo 📤 INSTRUCCIONES PARA SUBIR A LA WEB:
echo    1. Copia web_data.json a tu carpeta del proyecto GitHub
echo    2. Haz commit: git commit -m "Actualización datos trading"
echo    3. Sube cambios: git push origin main
echo    4. Netlify se actualizará automáticamente en 1-2 minutos
echo.

echo ⚠️  NOTA: Si usas datos de ejemplo, verifica la conexión con MT5
echo.

pause