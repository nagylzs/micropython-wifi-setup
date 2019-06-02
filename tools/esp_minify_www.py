import argparse
import os
import stat
import shutil
import gzip
import json
import re
import io

DEFAULT_EXCLUDE_EXTENSIONS = [".map"]


class Main:
    def __init__(self, args):
        self.args = args
        self.total_src_size = 0
        self.total_dst_size = 0

    def log(self, *params):
        if self.args.verbose:
            print(*params)

    @staticmethod
    def convert_index_html(data) -> str:
        all_styles = []
        hrefs = re.findall(r'href="([^\"]+)"', data)
        for href in hrefs:
            if href.endswith('.css'):
                all_styles.append(href)

        all_js = []
        all_embedded_js = []
        scripts = re.findall(r'<script([^>]*)>(.*?)</script>', data)
        for attribs, contents in scripts:
            if attribs:
                srcs = re.findall(r'src=\"([^+]+)\"', attribs)
                assert len(srcs) == 1
                all_js.append(srcs[0])
            else:
                all_embedded_js.append("<script>%s</script>" % contents)

        with io.StringIO() as fout:
            fout.write("""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width,initial-scale=1,shrink-to-fit=no"/>
    <meta name="theme-color" content="#000000"/>
    <title>Wifi Beállítása</title>
<body>
    <noscript>Az alkalmazás futtatásához JavaScript-re van szükség.</noscript>
    <div id="root"></div>
%(embedded_js)s
<script>
var root = document.getElementById("root");
var all_styles = %(all_styles)s;
var all_js = %(all_js)s;

var fetchStyle = function(index) {
  return new Promise((resolve, reject) => {
    if (index>=all_styles.length) {
        fetchJs(0).then(function() { resolve() });
    } else {
        var url = all_styles[index];    
        root.appendChild(document.createTextNode("."));
        let link = document.createElement('link');
        link.setAttribute('type', 'text/css');
        link.setAttribute('rel', 'stylesheet');
        link.onload = function() { 
            fetchStyle(index+1).then( function() { resolve(); } ) 
        };
        link.setAttribute('href', url);
        let headScript = document.querySelector('script');
        headScript.parentNode.insertBefore(link, headScript);
    }
  });
};

var fetchJs = function(index) {
  return new Promise((resolve, reject) => {
    if (index>=all_js.length) {
            resolve();
    } else {
        var url = all_js[index];
        root.appendChild(document.createTextNode("."));
        let link = document.createElement('script');
        link.setAttribute('type', 'text/javascript');
        link.onload = function() {
            fetchJs(index+1).then( function() { resolve(); } ) 
        };
        link.setAttribute('src', url);
        let headScript = document.querySelector('script');
        headScript.parentNode.insertBefore(link, headScript);
    }
  });
};

setTimeout(function() {fetchStyle(0)}, 1000);

</script>
</body>
</html>            
            """ % {
                "embedded_js": "\n".join(all_embedded_js),
                "all_styles": json.dumps(all_styles),
                "all_js": json.dumps(all_js),
            })
            fout.seek(0)
            return fout.read()

    def minify_dir(self, src_dir, dst_dir, is_root=False):
        for fname in sorted(os.listdir(src_dir)):
            src_path = os.path.join(src_dir, fname)
            dst_path = os.path.join(dst_dir, fname)
            if os.path.isdir(src_path):
                if not os.path.isdir(dst_path):
                    self.log("MKDIR", dst_path)
                    os.mkdir(dst_path)
                self.minify_dir(src_path, dst_path)
            else:
                src_ext = os.path.splitext(src_path)[1]
                if src_ext in self.args.exclude_extensions:
                    self.log("SKIP", src_path)
                    self.total_src_size += os.stat(src_path)[stat.ST_SIZE]
                else:
                    with open(src_path, "rb") as fin:
                        data = fin.read()
                    if is_root and fname == "index.html":
                        data = self.convert_index_html(data.decode("UTF-8")).encode("UTF-8")
                    src_size = len(data)
                    dst_size = src_size
                    if self.args.use_gzip and src_ext != ".gz":
                        compressed = gzip.compress(data)
                        if len(compressed) < len(data):
                            data = compressed
                            dst_size = len(compressed)
                            dst_path += ".gz"

                    with open(dst_path, "wb+") as fout:
                        fout.write(data)

                    self.total_src_size += src_size
                    self.total_dst_size += dst_size

                    percent = 100.0 * dst_size / src_size

                    self.log("COPY", src_path, "%.1f %%" % percent)

    def run(self):
        src_dir = self.args.src_dir
        dst_dir = self.args.dst_dir
        if not os.path.isdir(src_dir):
            parser.error("Source is not a directory: %s" % src_dir)
        if not os.path.isdir(args.dst_dir):
            parser.error("Destination is not a directory: %s" % dst_dir)

        if args.clean:
            for fname in os.listdir(dst_dir):
                if not fname in [os.pardir, os.curdir]:
                    fpath = os.path.join(dst_dir, fname)
                    if os.path.isfile(fpath):
                        self.log("RM", fpath)
                        os.unlink(fpath)
                    else:
                        self.log("RMTREE", fpath)
                        shutil.rmtree(fpath)

        self.total_src_size = 0
        self.total_dst_size = 0

        self.minify_dir(args.src_dir, args.dst_dir, True)

        if not self.total_dst_size:
            self.log("-----------------------------")
            self.log("Warning! No files???")
        else:
            percent = 100.0 * self.total_dst_size / self.total_src_size
            self.log("-----------------------------")
            self.log("Original size:   %.2fK" % (self.total_src_size / 1024.0))
            self.log("Minified size:   %.2fK" % (self.total_dst_size / 1024.0))
            self.log("Ratio:           %.2f%%" % percent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')

    parser.add_argument("-c", "--clean", dest='clean', action="store_true", default=False,
                        help="Clean output directory before minifying.")
    parser.add_argument("-v", "--verbose", dest='verbose', action="store_true", default=False,
                        help="Be verbose")
    parser.add_argument("-e", "--exclude", dest="exclude_extensions", action="append",
                        default=None,
                        help="Exclude files with this extension. Can be specified"
                             " multiple times. Default values is %s." % DEFAULT_EXCLUDE_EXTENSIONS)
    parser.add_argument("-n", "--no-gzip", dest='use_gzip', action="store_false", default=True,
                        help="Be verbose")

    parser.add_argument(dest='src_dir', help="Source directory")
    parser.add_argument(dest='dst_dir', help="Dest directory")

    args = parser.parse_args()
    if not args.exclude_extensions:
        args.exclude_extensions = DEFAULT_EXCLUDE_EXTENSIONS
    Main(args).run()
