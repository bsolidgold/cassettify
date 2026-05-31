class Cassettify < Formula
  include Language::Python::Virtualenv

  desc "Download your Spotify library to tagged, organized MP3s"
  homepage "https://github.com/bsolidgold/cassettify"
  url "https://files.pythonhosted.org/packages/source/c/cassettify/cassettify-0.1.0.tar.gz"
  sha256 "65eaa26398778ca8e08d29b299e23717dff9590349437f0434640ff4225f5f3b"
  license "MIT"

  depends_on "python@3.11"

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"cassettify", "--help"
  end
end
