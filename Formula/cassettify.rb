class Cassettify < Formula
  include Language::Python::Virtualenv

  desc "Download your Spotify playlists for your iPod Classic"
  homepage "https://github.com/bsolidgold/cassettify"
  url "https://files.pythonhosted.org/packages/source/c/cassettify/cassettify-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256_AFTER_PYPI_RELEASE"
  license "MIT"

  depends_on "python@3.11"

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"cassettify", "--help"
  end
end
