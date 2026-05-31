class Cassettify < Formula
  include Language::Python::Virtualenv

  desc "Download your Spotify library to tagged, organized MP3s"
  homepage "https://github.com/bsolidgold/cassettify"
  url "https://files.pythonhosted.org/packages/source/c/cassettify/cassettify-0.2.0.tar.gz"
  sha256 "ccd99691f31a84a3159265cf7398800993de7322bee0adbde9444292b79dadfd"
  license "MIT"

  depends_on "python@3.11"

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"cassettify", "--help"
  end
end
