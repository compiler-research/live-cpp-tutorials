#include <string>
#include <fstream>
#include <sstream>

#include "xeus/xbase64.hpp"
#include "xeus/xinterpreter.hpp"
#include "nlohmann/json.hpp"
#include "xcpp/xdisplay.hpp"

void show_image(std::string path, int width) {
    nlohmann::json bundle;
    bundle["text/html"] = "<img src='" + path + "' style='width: " + std::to_string(width) + "%;'>";
    xeus::get_interpreter().display_data(bundle, nlohmann::json::object(), nlohmann::json::object());
}

namespace nl = nlohmann;

namespace im
{
    struct image
    {   
        inline image(const std::string& filename)
        {
            std::ifstream fin(filename, std::ios::binary);   
            m_buffer << fin.rdbuf();
        }
        
        std::stringstream m_buffer;
    };
    
    nl::json mime_bundle_repr(const image& i)
    {
        auto bundle = nl::json::object();
        bundle["image/png"] = xeus::base64encode(i.m_buffer.str());
        return bundle;
    }
}