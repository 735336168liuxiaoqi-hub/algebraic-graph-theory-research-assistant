using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class DesktopLauncher {
    [STAThread]
    private static void Main() {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
        string entry = Path.Combine(root, "tools", "desktop_entry.py");
        if (!File.Exists(python) || !File.Exists(entry)) {
            MessageBox.Show("请将启动程序保留在科研助手项目目录中，并按桌面版说明配置Python环境。", "图论科研助手", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        try {
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = python;
            info.Arguments = "-X utf8 \"" + entry + "\"";
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            using (Process process = Process.Start(info)) {
                process.WaitForExit();
                if (process.ExitCode != 0) {
                    MessageBox.Show("桌面程序未能正常启动或退出。可查看 outputs\\desktop\\startup.log，或阅读 DESKTOP_APP.md 中的安装说明。", "图论科研助手", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
            }
        } catch (Exception error) {
            MessageBox.Show("无法启动科研助手：" + error.Message, "图论科研助手", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
