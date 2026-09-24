@echo off
setlocal
set "DIR=%~dp0"
set "JAVA_HOME=C:\Users\Server\soniccore-toolchain\jdk-21.0.12+8"
set "GRADLE_USER_HOME=%LOCALAPPDATA%\Gradle"
if not exist "%JAVA_HOME%\bin\java.exe" (
    echo ERROR: Java not found at %%JAVA_HOME%%
    exit /b 1
)
"%JAVA_HOME%\bin\java.exe" -classpath "%DIR%\gradle\wrapper\gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain %*
