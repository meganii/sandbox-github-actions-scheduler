library(dplyr)
library(ggplot2)
library(ggtext)
library(png)
library(ggimage)

df <- read.csv("./R/data.csv", stringsAsFactors = F)
df$Start  <- as.Date(df$Start, format = "%Y-%m-%d", origin="1970-01-01")
df$End  <- as.Date(df$End, format = "%Y-%m-%d", origin="1970-01-01")
df

orderedName <- df %>%
  group_by(Name) %>%
  top_n(-1, Start)
orderedName
orderedName <- mutate(orderedName, Image = paste0("./R/icons/", Name, ".png"))

df2 <- data.frame(Start=df$Start, End=df$End, Name = factor(df$Name, levels=orderedName$Name))

p <- ggplot(df2, aes(Start, Name)) +
  geom_linerange(aes(xmin = Start, xmax = End, colour=Name)) +
  geom_point(aes(x=Start, colour=Name)) +
  geom_point(aes(x=End, colour=Name)) +
  geom_image(data=orderedName, aes(x=Start, y=Name, image=Image), size=0.02) +
  geom_text(data=orderedName, aes(x=Start-15, y=Name, vjust=0.5, hjust=1),label=orderedName$Name, size=3) + 
  scale_x_date(date_labels = "%Y/%m", breaks = "6 months", minor_breaks = "1 month") + 
  theme_bw() + 
  theme(legend.position = "none",
        axis.text.y = element_blank(),
        axis.title = element_blank(),
        axis.ticks.y = element_blank(),
        panel.grid.major.y = element_blank()
        )

ggsave(file = "./images/activeusers.png", plot = p)
  
